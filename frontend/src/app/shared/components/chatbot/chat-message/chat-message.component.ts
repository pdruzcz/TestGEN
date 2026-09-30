import { Component, computed, inject, input } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";
import { RouterLink } from "@angular/router";
import { ChatMessage, ChatbotService } from "../../../services/chatbot.service";

/**
 * Story 6.14, Task 2 — pojedyncza wiadomość: avatar, treść z klikalnymi
 * referencjami (AC3), godzina i kursor strumieniowania (AC7).
 */
@Component({
  selector: "app-chat-message",
  standalone: true,
  imports: [MatIconModule, RouterLink],
  templateUrl: "./chat-message.component.html",
  styleUrls: ["./chat-message.component.scss"],
})
export class ChatMessageComponent {
  private readonly chatbot = inject(ChatbotService);

  readonly message = input.required<ChatMessage>();

  readonly segments = computed(() => this.chatbot.parseSegments(this.message().content));

  readonly isUser = computed(() => this.message().role === "user");

  readonly avatarLabel = computed(() => (this.isUser() ? "Ty" : "Asystent AI"));

  readonly avatarIcon = computed(() => (this.isUser() ? "person" : "smart_toy"));

  /** Godzina w formacie 24h — spójna z resztą interfejsu (pl-PL). */
  readonly time = computed(() =>
    new Date(this.message().timestamp).toLocaleTimeString("pl-PL", {
      hour: "2-digit",
      minute: "2-digit",
    }),
  );
}
