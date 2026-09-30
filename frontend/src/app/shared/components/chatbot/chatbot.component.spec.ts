import { signal } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { LiveAnnouncerService } from "../../services/live-announcer.service";
import { ChatMessage, ChatSegment, ChatbotService } from "../../services/chatbot.service";
import { ChatbotComponent } from "./chatbot.component";

class FakeChatbotService {
  readonly messagesSignal = signal<ChatMessage[]>([]);
  readonly isOpenSignal = signal(false);
  readonly isLoadingSignal = signal(false);
  readonly sent: string[] = [];
  cleared = 0;

  toggle(): void {
    this.isOpenSignal.update((open) => !open);
  }

  close(): void {
    this.isOpenSignal.set(false);
  }

  clearHistory(): void {
    this.cleared += 1;
    this.messagesSignal.set([]);
  }

  async sendMessage(text: string): Promise<void> {
    this.sent.push(text);
  }

  parseSegments(content: string): ChatSegment[] {
    return [{ kind: "text", text: content }];
  }
}

function message(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "m-1",
    role: "assistant",
    content: "Masz 3 luki.",
    timestamp: "2026-07-28T09:05:00.000Z",
    ...overrides,
  };
}

describe("ChatbotComponent", () => {
  let fixture: ComponentFixture<ChatbotComponent>;
  let service: FakeChatbotService;
  let announced: string[];

  beforeEach(async () => {
    service = new FakeChatbotService();
    announced = [];

    await TestBed.configureTestingModule({
      imports: [ChatbotComponent],
      providers: [
        provideRouter([]),
        { provide: ChatbotService, useValue: service },
        {
          provide: LiveAnnouncerService,
          useValue: { announce: (text: string) => announced.push(text) },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatbotComponent);
    fixture.detectChanges();
  });

  const el = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const trigger = (): HTMLButtonElement =>
    el().querySelector(".chatbot-trigger") as HTMLButtonElement;
  const panel = (): HTMLElement | null => el().querySelector('[role="dialog"]');

  function open(): void {
    trigger().click();
    fixture.detectChanges();
  }

  describe("panel (AC1)", () => {
    it("startuje z zamkniętym panelem", () => {
      expect(panel()).toBeNull();
      expect(trigger().getAttribute("aria-expanded")).toBe("false");
    });

    it("opisuje przycisk otwierający po polsku", () => {
      expect(trigger().getAttribute("aria-label")).toBe("Asystent AI");
    });

    it("otwiera panel dialogu po kliknięciu ikony", () => {
      open();

      expect(panel()).not.toBeNull();
      expect(panel()?.getAttribute("aria-label")).toBe("Asystent AI");
      expect(trigger().getAttribute("aria-expanded")).toBe("true");
    });

    it("nie blokuje głównej treści (aria-modal=false)", () => {
      open();

      expect(panel()?.getAttribute("aria-modal")).toBe("false");
    });

    it("zamyka panel przyciskiem zamknięcia", () => {
      open();
      (el().querySelector(".chatbot-close") as HTMLButtonElement).click();
      fixture.detectChanges();

      expect(panel()).toBeNull();
    });
  });

  describe("klawiatura i fokus (AC4)", () => {
    it("Escape zamyka panel i przywraca fokus do przycisku", () => {
      open();
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
      fixture.detectChanges();

      expect(panel()).toBeNull();
      expect(document.activeElement).toBe(trigger());
    });

    it("ignoruje Escape gdy panel jest zamknięty", () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
      fixture.detectChanges();

      expect(panel()).toBeNull();
    });

    it("przenosi fokus do pola wiadomości po otwarciu", () => {
      open();

      expect(document.activeElement).toBe(el().querySelector("textarea"));
    });

    it("zapętla Tab wewnątrz panelu", () => {
      open();
      const focusable = Array.from(
        panel()?.querySelectorAll<HTMLElement>("button, textarea") ?? [],
      ).filter((node) => !(node as HTMLButtonElement).disabled);
      const last = focusable[focusable.length - 1];
      last.focus();

      panel()?.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
      fixture.detectChanges();

      expect(document.activeElement).toBe(focusable[0]);
    });

    it("zapętla Shift+Tab wstecz wewnątrz panelu", () => {
      open();
      const focusable = Array.from(
        panel()?.querySelectorAll<HTMLElement>("button, textarea") ?? [],
      ).filter((node) => !(node as HTMLButtonElement).disabled);
      focusable[0].focus();

      panel()?.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true }),
      );
      fixture.detectChanges();

      expect(document.activeElement).toBe(focusable[focusable.length - 1]);
    });
  });

  describe("wiadomości (AC2, AC5)", () => {
    it("renderuje historię rozmowy", () => {
      service.messagesSignal.set([
        message({ id: "u-1", role: "user", content: "Ile mam luk?" }),
        message({ id: "a-1" }),
      ]);
      open();

      expect(el().querySelectorAll("app-chat-message")).toHaveLength(2);
    });

    it("udostępnia region aria-live dla nowych odpowiedzi", () => {
      open();

      expect(el().querySelector(".chatbot-log")?.getAttribute("aria-live")).toBe("polite");
    });

    it("ogłasza zakończoną odpowiedź asystenta", () => {
      open();
      service.messagesSignal.set([message({ streaming: false })]);
      fixture.detectChanges();

      expect(announced).toContain("Masz 3 luki.");
    });

    it("nie ogłasza odpowiedzi w trakcie strumieniowania", () => {
      open();
      service.messagesSignal.set([message({ streaming: true, content: "Masz " })]);
      fixture.detectChanges();

      expect(announced).toEqual([]);
    });

    it("przekazuje wiadomość z pola wejściowego do serwisu", () => {
      open();
      const textarea = el().querySelector("textarea") as HTMLTextAreaElement;
      textarea.value = "Ile mam luk?";
      textarea.dispatchEvent(new Event("input"));
      textarea.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", cancelable: true }));
      fixture.detectChanges();

      expect(service.sent).toEqual(["Ile mam luk?"]);
    });

    it("pokazuje komunikat powitalny przy pustej historii", () => {
      open();

      expect(el().querySelector(".chatbot-empty")?.textContent).toMatch(/zadaj pytanie/i);
    });

    it("czyści historię przyciskiem", () => {
      service.messagesSignal.set([message()]);
      open();
      (el().querySelector(".chatbot-clear") as HTMLButtonElement).click();
      fixture.detectChanges();

      expect(service.cleared).toBe(1);
    });
  });
});
