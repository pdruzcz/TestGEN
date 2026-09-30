import {
  ChangeDetectorRef,
  Component,
  ElementRef,
  HostListener,
  effect,
  inject,
  viewChild,
} from "@angular/core";
import { MatIconModule } from "@angular/material/icon";
import { ChatbotService } from "../../services/chatbot.service";
import { LiveAnnouncerService } from "../../services/live-announcer.service";
import { ChatInputComponent } from "./chat-input/chat-input.component";
import { ChatMessageComponent } from "./chat-message/chat-message.component";

const FOCUSABLE =
  'button:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';

/**
 * Story 6.14, Task 1 — panel asystenta AI dostępny na każdej stronie.
 *
 * Panel jest niemodalny (`aria-modal="false"`) — nie blokuje głównej treści,
 * ale pułapka fokusu utrzymuje nawigację klawiaturą wewnątrz otwartego okna,
 * a Escape zamyka panel i przywraca fokus do przycisku (AC4).
 */
@Component({
  selector: "app-chatbot",
  standalone: true,
  imports: [MatIconModule, ChatMessageComponent, ChatInputComponent],
  templateUrl: "./chatbot.component.html",
  styleUrls: ["./chatbot.component.scss"],
})
export class ChatbotComponent {
  private readonly chatbot = inject(ChatbotService);
  private readonly announcer = inject(LiveAnnouncerService);
  private readonly changeDetector = inject(ChangeDetectorRef);

  readonly messages = this.chatbot.messagesSignal;
  readonly isOpen = this.chatbot.isOpenSignal;
  readonly isLoading = this.chatbot.isLoadingSignal;

  private readonly trigger = viewChild.required<ElementRef<HTMLButtonElement>>("trigger");
  private readonly panel = viewChild<ElementRef<HTMLElement>>("panel");
  private readonly input = viewChild(ChatInputComponent);

  private announcedId?: string;

  constructor() {
    // Ogłaszamy wyłącznie ukończone odpowiedzi — kolejne tokeny w trakcie
    // strumieniowania zalałyby screen reader powtórzeniami (AC5, AC7).
    effect(() => {
      const last = this.messages().at(-1);
      if (!last || last.role !== "assistant" || last.streaming || !last.content) {
        return;
      }
      if (last.id !== this.announcedId) {
        this.announcedId = last.id;
        void this.announcer.announce(last.content);
      }
    });
  }

  toggle(): void {
    this.chatbot.toggle();
    if (!this.isOpen()) {
      return;
    }
    // Panel powstaje dopiero po odświeżeniu widoku, więc fokus (AC4)
    // przenosimy dopiero po wyrenderowaniu jego zawartości.
    this.changeDetector.detectChanges();
    this.input()?.focus();
  }

  close(): void {
    this.chatbot.close();
    this.trigger().nativeElement.focus();
  }

  clear(): void {
    this.chatbot.clearHistory();
  }

  onSend(text: string): void {
    void this.chatbot.sendMessage(text);
  }

  @HostListener("document:keydown.escape")
  onEscape(): void {
    if (this.isOpen()) {
      this.close();
    }
  }

  onPanelKeydown(event: KeyboardEvent): void {
    if (event.key !== "Tab") {
      return;
    }

    const panel = this.panel()?.nativeElement;
    if (!panel) {
      return;
    }

    const nodes = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (nodes.length === 0) {
      return;
    }

    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    const active = document.activeElement;

    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }
}
