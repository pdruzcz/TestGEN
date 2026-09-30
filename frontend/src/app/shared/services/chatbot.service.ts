import { Injectable, inject, signal } from "@angular/core";
import { Router } from "@angular/router";
import { ChatRequestContext, LlmGatewayService } from "./llm-gateway.service";

/** Klucz historii rozmowy w localStorage (Story 6.14, AC6). */
export const CHAT_HISTORY_STORAGE_KEY = "testgen:chat-history";

/** Limit przechowywanych wiadomości — nadmiar usuwany FIFO (AC6). */
export const MAX_STORED_MESSAGES = 100;

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  /** Odpowiedź jest w trakcie strumieniowania — sterowanie animacją kursora (AC7). */
  streaming?: boolean;
  isError?: boolean;
}

/** Fragment odpowiedzi: zwykły tekst albo klikalna referencja (AC3). */
export type ChatSegment =
  | { kind: "text"; text: string }
  | { kind: "ref"; text: string; label: string; link: string[] };

/** Typy referencji `@ref:{typ}:{id}` rozpoznawane w odpowiedziach modelu. */
const REF_PATTERN = /@ref:(tc|finding|report):(\d+)/g;

const REF_LABELS: Record<string, string> = {
  tc: "przypadek testowy",
  finding: "wynik analizy",
  report: "raport",
};

/**
 * Story 6.14, Task 4 — stan czatu, historia i parsowanie referencji.
 *
 * Referencje kierują na istniejące trasy projektowe (`app.routes.ts`):
 * wyniki i raporty nie mają tras dla pojedynczego elementu, więc prowadzą
 * do widoku listy w kontekście bieżącego projektu.
 */
@Injectable({ providedIn: "root" })
export class ChatbotService {
  private readonly gateway = inject(LlmGatewayService);
  private readonly router = inject(Router);

  private readonly messages = signal<ChatMessage[]>(this.restoreHistory());
  private readonly isOpen = signal(false);
  private readonly isLoading = signal(false);
  private conversationId?: string;

  readonly messagesSignal = this.messages.asReadonly();
  readonly isOpenSignal = this.isOpen.asReadonly();
  readonly isLoadingSignal = this.isLoading.asReadonly();

  toggle(): void {
    this.isOpen.update((open) => !open);
  }

  open(): void {
    this.isOpen.set(true);
  }

  close(): void {
    this.isOpen.set(false);
  }

  clearHistory(): void {
    this.messages.set([]);
    this.conversationId = undefined;
    localStorage.removeItem(CHAT_HISTORY_STORAGE_KEY);
  }

  /** Wysyła pytanie i dopisuje odpowiedź asystenta w miarę napływu tokenów. */
  async sendMessage(text: string): Promise<void> {
    const message = text.trim();
    if (!message || this.isLoading()) {
      return;
    }

    this.isLoading.set(true);
    const answerId = this.nextId();
    this.messages.update((current) => [
      ...current,
      this.createMessage("user", message),
      { ...this.createMessage("assistant", ""), id: answerId, streaming: true },
    ]);

    try {
      for await (const event of this.gateway.streamMessage({
        message,
        conversationId: this.conversationId,
        context: this.currentContext(),
      })) {
        switch (event.type) {
          case "token":
            this.patch(answerId, (m) => ({ ...m, content: m.content + event.content }));
            break;
          case "done":
            this.conversationId = event.conversationId || this.conversationId;
            this.patch(answerId, (m) => ({
              ...m,
              content: event.content || m.content,
            }));
            break;
          case "error":
            this.patch(answerId, (m) => ({
              ...m,
              content: event.message,
              isError: true,
            }));
            break;
        }
      }
    } finally {
      this.patch(answerId, (m) => ({ ...m, streaming: false }));
      this.isLoading.set(false);
      this.persistHistory();
    }
  }

  /**
   * Rozbija treść odpowiedzi na fragmenty tekstu i referencji.
   * Poza kontekstem projektu referencje zostają zwykłym tekstem — nie ma
   * dokąd nawigować.
   */
  parseSegments(content: string): ChatSegment[] {
    const projectId = this.currentProjectId();
    if (!projectId) {
      return [{ kind: "text", text: content }];
    }

    const segments: ChatSegment[] = [];
    let cursor = 0;

    for (const match of content.matchAll(REF_PATTERN)) {
      const [raw, type, id] = match;
      const start = match.index;
      if (start > cursor) {
        segments.push({ kind: "text", text: content.slice(cursor, start) });
      }
      segments.push({
        kind: "ref",
        text: raw,
        label: `${REF_LABELS[type]} #${id}`,
        link: this.refLink(projectId, type, id),
      });
      cursor = start + raw.length;
    }

    if (cursor < content.length) {
      segments.push({ kind: "text", text: content.slice(cursor) });
    }

    return segments;
  }

  private refLink(projectId: string, type: string, id: string): string[] {
    const base = ["/projects", projectId];
    switch (type) {
      case "tc":
        return [...base, "test-cases", id];
      case "report":
        return [...base, "reports"];
      default:
        return [...base, "results"];
    }
  }

  private currentContext(): ChatRequestContext | undefined {
    const projectId = this.currentProjectId();
    return projectId ? { projectId, view: this.router.url } : undefined;
  }

  private currentProjectId(): string | undefined {
    return /\/projects\/([^/?#]+)/.exec(this.router.url)?.[1];
  }

  private patch(id: string, update: (message: ChatMessage) => ChatMessage): void {
    this.messages.update((current) =>
      current.map((message) => (message.id === id ? update(message) : message)),
    );
  }

  private createMessage(role: ChatMessage["role"], content: string): ChatMessage {
    return {
      id: this.nextId(),
      role,
      content,
      timestamp: new Date().toISOString(),
    };
  }

  private nextId(): string {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  }

  private persistHistory(): void {
    const trimmed = this.messages().slice(-MAX_STORED_MESSAGES);
    localStorage.setItem(CHAT_HISTORY_STORAGE_KEY, JSON.stringify(trimmed));
  }

  private restoreHistory(): ChatMessage[] {
    const raw = localStorage.getItem(CHAT_HISTORY_STORAGE_KEY);
    if (!raw) {
      return [];
    }

    try {
      const parsed: unknown = JSON.parse(raw);
      return Array.isArray(parsed)
        ? (parsed as ChatMessage[]).slice(-MAX_STORED_MESSAGES)
        : [];
    } catch {
      return [];
    }
  }
}
