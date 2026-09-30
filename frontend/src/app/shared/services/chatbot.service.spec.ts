import { TestBed } from "@angular/core/testing";
import { Router } from "@angular/router";
import {
  CHAT_HISTORY_STORAGE_KEY,
  ChatbotService,
  MAX_STORED_MESSAGES,
} from "./chatbot.service";
import { ChatStreamEvent, LlmGatewayService } from "./llm-gateway.service";

class FakeGateway {
  events: ChatStreamEvent[] = [];
  lastRequest: unknown;

  async *streamMessage(request: unknown): AsyncGenerator<ChatStreamEvent> {
    this.lastRequest = request;
    for (const event of this.events) {
      yield event;
    }
  }
}

const OK_STREAM: ChatStreamEvent[] = [
  { type: "token", content: "Masz " },
  { type: "token", content: "3 luki." },
  { type: "done", conversationId: "c-1", content: "Masz 3 luki." },
];

describe("ChatbotService", () => {
  let service: ChatbotService;
  let gateway: FakeGateway;
  let url: string;

  beforeEach(() => {
    localStorage.clear();
    gateway = new FakeGateway();
    url = "/projects/p-9/results";

    TestBed.configureTestingModule({
      providers: [
        { provide: LlmGatewayService, useValue: gateway },
        {
          provide: Router,
          useValue: {
            get url() {
              return url;
            },
          },
        },
      ],
    });
    service = TestBed.inject(ChatbotService);
  });

  describe("panel", () => {
    it("startuje zamknięty", () => {
      expect(service.isOpenSignal()).toBe(false);
    });

    it("przełącza widoczność", () => {
      service.toggle();
      expect(service.isOpenSignal()).toBe(true);
      service.toggle();
      expect(service.isOpenSignal()).toBe(false);
    });
  });

  describe("sendMessage", () => {
    it("dodaje wiadomość użytkownika i odpowiedź asystenta", async () => {
      gateway.events = OK_STREAM;

      await service.sendMessage("Ile mam luk?");

      const messages = service.messagesSignal();
      expect(messages).toHaveLength(2);
      expect(messages[0]).toMatchObject({ role: "user", content: "Ile mam luk?" });
      expect(messages[1]).toMatchObject({ role: "assistant", content: "Masz 3 luki." });
    });

    it("skleja tokeny progresywnie w treść odpowiedzi", async () => {
      gateway.events = OK_STREAM;
      const snapshots: string[] = [];

      const done = service.sendMessage("test");
      snapshots.push(service.messagesSignal().at(-1)?.content ?? "");
      await done;
      snapshots.push(service.messagesSignal().at(-1)?.content ?? "");

      expect(snapshots.at(-1)).toBe("Masz 3 luki.");
    });

    it("czyści flagę streamingu po zakończeniu", async () => {
      gateway.events = OK_STREAM;

      await service.sendMessage("test");

      expect(service.messagesSignal().at(-1)?.streaming).toBe(false);
      expect(service.isLoadingSignal()).toBe(false);
    });

    it("ignoruje pustą wiadomość", async () => {
      await service.sendMessage("   ");
      expect(service.messagesSignal()).toHaveLength(0);
    });

    it("dołącza kontekst projektu z adresu URL", async () => {
      gateway.events = OK_STREAM;

      await service.sendMessage("test");

      expect(gateway.lastRequest).toMatchObject({
        context: { projectId: "p-9" },
      });
    });

    it("przekazuje conversationId kolejnej wiadomości", async () => {
      gateway.events = OK_STREAM;
      await service.sendMessage("pierwsze");
      await service.sendMessage("drugie");

      expect(gateway.lastRequest).toMatchObject({ conversationId: "c-1" });
    });

    it("oznacza odpowiedź jako błąd przy zdarzeniu error", async () => {
      gateway.events = [
        { type: "error", code: "rate_limit", message: "Przekroczono limit zapytań." },
      ];

      await service.sendMessage("test");

      expect(service.messagesSignal().at(-1)).toMatchObject({
        role: "assistant",
        isError: true,
        content: "Przekroczono limit zapytań.",
      });
    });
  });

  describe("historia w localStorage", () => {
    it("zapisuje historię po zakończeniu odpowiedzi", async () => {
      gateway.events = OK_STREAM;

      await service.sendMessage("test");

      const stored = JSON.parse(localStorage.getItem(CHAT_HISTORY_STORAGE_KEY) ?? "[]");
      expect(stored).toHaveLength(2);
    });

    it("odtwarza historię przy starcie serwisu", async () => {
      gateway.events = OK_STREAM;
      await service.sendMessage("test");

      TestBed.resetTestingModule();
      TestBed.configureTestingModule({
        providers: [
          { provide: LlmGatewayService, useValue: gateway },
          { provide: Router, useValue: { url } },
        ],
      });

      expect(TestBed.inject(ChatbotService).messagesSignal()).toHaveLength(2);
    });

    it("przycina historię do limitu wiadomości (FIFO)", () => {
      const overflow = Array.from({ length: MAX_STORED_MESSAGES + 10 }, (_, i) => ({
        id: String(i),
        role: "user",
        content: `wiadomość ${i}`,
        timestamp: new Date().toISOString(),
      }));
      localStorage.setItem(CHAT_HISTORY_STORAGE_KEY, JSON.stringify(overflow));

      TestBed.resetTestingModule();
      TestBed.configureTestingModule({
        providers: [
          { provide: LlmGatewayService, useValue: gateway },
          { provide: Router, useValue: { url } },
        ],
      });
      const messages = TestBed.inject(ChatbotService).messagesSignal();

      expect(messages).toHaveLength(MAX_STORED_MESSAGES);
      expect(messages[0].content).toBe("wiadomość 10");
    });

    it("znosi uszkodzoną zawartość localStorage", () => {
      localStorage.setItem(CHAT_HISTORY_STORAGE_KEY, "{nie-json");

      TestBed.resetTestingModule();
      TestBed.configureTestingModule({
        providers: [
          { provide: LlmGatewayService, useValue: gateway },
          { provide: Router, useValue: { url } },
        ],
      });

      expect(TestBed.inject(ChatbotService).messagesSignal()).toEqual([]);
    });

    it("czyści historię na żądanie", async () => {
      gateway.events = OK_STREAM;
      await service.sendMessage("test");

      service.clearHistory();

      expect(service.messagesSignal()).toEqual([]);
      expect(localStorage.getItem(CHAT_HISTORY_STORAGE_KEY)).toBeNull();
    });
  });

  describe("parseSegments — referencje @ref:{typ}:{id}", () => {
    it("zwraca sam tekst gdy brak referencji", () => {
      expect(service.parseSegments("Zwykła odpowiedź.")).toEqual([
        { kind: "text", text: "Zwykła odpowiedź." },
      ]);
    });

    it("rozpoznaje referencję do przypadku testowego", () => {
      const segments = service.parseSegments("Sprawdź @ref:tc:15 proszę.");

      expect(segments).toHaveLength(3);
      expect(segments[1]).toMatchObject({
        kind: "ref",
        link: ["/projects", "p-9", "test-cases", "15"],
      });
    });

    it("kieruje referencję do wyniku na widok wyników projektu", () => {
      const segments = service.parseSegments("Zobacz @ref:finding:42");

      expect(segments[1]).toMatchObject({
        kind: "ref",
        link: ["/projects", "p-9", "results"],
      });
    });

    it("kieruje referencję do raportu na widok raportów", () => {
      const segments = service.parseSegments("@ref:report:7");

      expect(segments[0]).toMatchObject({
        kind: "ref",
        link: ["/projects", "p-9", "reports"],
      });
    });

    it("nadaje referencji czytelną etykietę po polsku", () => {
      const [, ref] = service.parseSegments("Sprawdź @ref:tc:15.") as any[];
      expect(ref.label).toBe("przypadek testowy #15");
    });

    it("rozpoznaje wiele referencji w jednej odpowiedzi", () => {
      const segments = service.parseSegments("@ref:tc:1 oraz @ref:tc:2");
      expect(segments.filter((s) => s.kind === "ref")).toHaveLength(2);
    });

    it("pozostawia nieznany typ referencji jako tekst", () => {
      expect(service.parseSegments("@ref:nieznany:1")).toEqual([
        { kind: "text", text: "@ref:nieznany:1" },
      ]);
    });

    it("pozostawia referencję jako tekst poza kontekstem projektu", () => {
      url = "/dashboard";

      expect(service.parseSegments("@ref:tc:15")).toEqual([
        { kind: "text", text: "@ref:tc:15" },
      ]);
    });
  });
});
