import { Component, ElementRef, input, output, signal, viewChild } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";

/**
 * Story 6.14, Task 3 — pole wprowadzania wiadomości: auto-resize,
 * Enter wysyła, Shift+Enter dodaje nową linię.
 */
@Component({
  selector: "app-chat-input",
  standalone: true,
  imports: [MatIconModule],
  templateUrl: "./chat-input.component.html",
  styleUrls: ["./chat-input.component.scss"],
})
export class ChatInputComponent {
  readonly disabled = input(false);
  readonly send = output<string>();

  readonly value = signal("");

  private readonly field = viewChild.required<ElementRef<HTMLTextAreaElement>>("field");

  focus(): void {
    this.field().nativeElement.focus();
  }

  onInput(event: Event): void {
    const textarea = event.target as HTMLTextAreaElement;
    this.value.set(textarea.value);
    this.resize(textarea);
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }
    event.preventDefault();
    this.submit();
  }

  submit(): void {
    const text = this.value().trim();
    if (!text || this.disabled()) {
      return;
    }

    this.send.emit(text);
    this.value.set("");
    const textarea = this.field().nativeElement;
    textarea.value = "";
    this.resize(textarea);
  }

  /** Dopasowuje wysokość do treści — reset przed pomiarem, by pole mogło się skurczyć. */
  private resize(textarea: HTMLTextAreaElement): void {
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }
}
