import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ChatInputComponent } from "./chat-input.component";

describe("ChatInputComponent", () => {
  let fixture: ComponentFixture<ChatInputComponent>;
  let sent: string[];

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatInputComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatInputComponent);
    sent = [];
    fixture.componentInstance.send.subscribe((value: string) => sent.push(value));
    fixture.componentRef.setInput("disabled", false);
    fixture.detectChanges();
  });

  const textarea = (): HTMLTextAreaElement =>
    fixture.nativeElement.querySelector("textarea");

  const sendButton = (): HTMLButtonElement =>
    fixture.nativeElement.querySelector(".chat-input__send");

  function type(value: string): void {
    const field = textarea();
    field.value = value;
    field.dispatchEvent(new Event("input"));
    fixture.detectChanges();
  }

  function press(key: string, shiftKey = false): KeyboardEvent {
    const event = new KeyboardEvent("keydown", { key, shiftKey, cancelable: true });
    textarea().dispatchEvent(event);
    fixture.detectChanges();
    return event;
  }

  it("wysyła treść po naciśnięciu Enter", () => {
    type("Ile mam luk?");
    press("Enter");

    expect(sent).toEqual(["Ile mam luk?"]);
  });

  it("czyści pole po wysłaniu", () => {
    type("Ile mam luk?");
    press("Enter");

    expect(textarea().value).toBe("");
  });

  it("Shift+Enter wstawia nową linię zamiast wysyłać", () => {
    type("pierwsza linia");
    const event = press("Enter", true);

    expect(sent).toEqual([]);
    expect(event.defaultPrevented).toBe(false);
  });

  it("nie wysyła pustej treści", () => {
    type("   ");
    press("Enter");
    sendButton().click();

    expect(sent).toEqual([]);
  });

  it("wysyła po kliknięciu przycisku Wyślij", () => {
    type("pytanie");
    sendButton().click();

    expect(sent).toEqual(["pytanie"]);
  });

  it("blokuje wysyłkę gdy trwa odpowiedź", () => {
    fixture.componentRef.setInput("disabled", true);
    type("pytanie");
    press("Enter");

    expect(sent).toEqual([]);
    expect(sendButton().disabled).toBe(true);
  });

  it("opisuje pole i przycisk etykietami po polsku", () => {
    expect(textarea().getAttribute("aria-label")).toBe("Treść wiadomości");
    expect(sendButton().getAttribute("aria-label")).toBe("Wyślij wiadomość");
  });

  it("dopasowuje wysokość pola do treści", () => {
    const field = textarea();
    Object.defineProperty(field, "scrollHeight", { value: 96, configurable: true });

    type("wiersz\nwiersz\nwiersz");

    expect(field.style.height).toBe("96px");
  });
});
