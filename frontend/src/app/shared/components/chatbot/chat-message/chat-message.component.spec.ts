import { signal } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { ChatMessage, ChatSegment, ChatbotService } from "../../../services/chatbot.service";
import { ChatMessageComponent } from "./chat-message.component";

class FakeChatbotService {
  segments: ChatSegment[] = [];
  parseSegments(): ChatSegment[] {
    return this.segments;
  }
}

const BASE: ChatMessage = {
  id: "m-1",
  role: "assistant",
  content: "Masz 3 luki.",
  timestamp: "2026-07-28T09:05:00.000Z",
};

describe("ChatMessageComponent", () => {
  let fixture: ComponentFixture<ChatMessageComponent>;
  let service: FakeChatbotService;

  beforeEach(async () => {
    service = new FakeChatbotService();
    service.segments = [{ kind: "text", text: BASE.content }];

    await TestBed.configureTestingModule({
      imports: [ChatMessageComponent],
      providers: [provideRouter([]), { provide: ChatbotService, useValue: service }],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatMessageComponent);
  });

  function render(message: Partial<ChatMessage> = {}): HTMLElement {
    fixture.componentRef.setInput("message", { ...BASE, ...message });
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it("wyświetla treść odpowiedzi asystenta", () => {
    expect(render().querySelector(".chat-message__text")?.textContent).toContain(
      "Masz 3 luki.",
    );
  });

  it("rozróżnia autora wiadomości klasą i etykietą avatara", () => {
    const el = render({ role: "user", content: "Ile mam luk?" });

    expect(el.querySelector(".chat-message")?.classList).toContain("chat-message--user");
    expect(el.querySelector(".chat-message__avatar")?.getAttribute("aria-label")).toBe("Ty");
  });

  it("opisuje avatar asystenta po polsku", () => {
    expect(render().querySelector(".chat-message__avatar")?.getAttribute("aria-label")).toBe(
      "Asystent AI",
    );
  });

  it("renderuje referencję jako link nawigacyjny (AC3)", () => {
    service.segments = [
      { kind: "text", text: "Sprawdź " },
      {
        kind: "ref",
        text: "@ref:tc:15",
        label: "przypadek testowy #15",
        link: ["/projects", "p-9", "test-cases", "15"],
      },
    ];

    const link = render().querySelector("a.chat-ref") as HTMLAnchorElement;

    expect(link.getAttribute("href")).toBe("/projects/p-9/test-cases/15");
    expect(link.textContent?.trim()).toBe("przypadek testowy #15");
  });

  it("pokazuje kursor podczas strumieniowania (AC7)", () => {
    expect(render({ streaming: true }).querySelector(".chat-message__cursor")).not.toBeNull();
  });

  it("ukrywa kursor po zakończeniu odpowiedzi", () => {
    expect(render({ streaming: false }).querySelector(".chat-message__cursor")).toBeNull();
  });

  it("wyświetla godzinę wiadomości w elemencie time", () => {
    const time = render().querySelector("time") as HTMLTimeElement;

    expect(time.getAttribute("datetime")).toBe(BASE.timestamp);
    expect(time.textContent?.trim()).toMatch(/\d{2}:\d{2}/);
  });

  it("oznacza odpowiedź błędną osobną klasą", () => {
    const el = render({ isError: true, content: "Przekroczono limit zapytań." });

    expect(el.querySelector(".chat-message")?.classList).toContain("chat-message--error");
  });
});

describe("ChatMessageComponent — sygnał wejściowy", () => {
  it("przelicza segmenty po zmianie treści", async () => {
    const segments = signal<ChatSegment[]>([{ kind: "text", text: "a" }]);
    await TestBed.configureTestingModule({
      imports: [ChatMessageComponent],
      providers: [
        provideRouter([]),
        { provide: ChatbotService, useValue: { parseSegments: () => segments() } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(ChatMessageComponent);
    fixture.componentRef.setInput("message", BASE);
    fixture.detectChanges();

    segments.set([{ kind: "text", text: "ab" }]);
    fixture.componentRef.setInput("message", { ...BASE, content: "ab" });
    fixture.detectChanges();

    expect(
      (fixture.nativeElement as HTMLElement).querySelector(".chat-message__text")?.textContent,
    ).toContain("ab");
  });
});
