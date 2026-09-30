import { Injectable } from "@angular/core";
import { environment } from "../../../environments/environment";

/** Kontekst widoku dołączany do pytania (Story 6.14, AC3). */
export interface ChatRequestContext {
  projectId?: string;
  view?: string;
}

export interface ChatStreamRequest {
  message: string;
  conversationId?: string;
  context?: ChatRequestContext;
}

/** Zdarzenie strumienia SSE z endpointu `/chat/message`. */
export type ChatStreamEvent =
  | { type: "token"; content: string }
  | { type: "done"; conversationId: string; content: string }
  | { type: "error"; code: string; message: string };

const GENERIC_ERROR = "Nie udało się uzyskać odpowiedzi od asystenta.";
const NETWORK_ERROR =
  "Brak połączenia z serwerem. Sprawdź sieć i spróbuj ponownie.";

/**
 * Story 6.14, Task 5 — transport SSE do LLM Gateway.
 *
 * `HttpClient` buforuje całą odpowiedź, więc progresywne renderowanie (AC7)
 * wymaga `fetch` + `ReadableStream`. Sesja jest cookie-based (HttpOnly JWT),
 * stąd `credentials: "include"` zamiast nagłówka Authorization.
 */
@Injectable({ providedIn: "root" })
export class LlmGatewayService {
  private readonly endpoint = `${environment.apiUrl}/chat/message`;

  /** Strumieniuje odpowiedź asystenta jako kolejne zdarzenia. */
  async *streamMessage(
    request: ChatStreamRequest,
  ): AsyncGenerator<ChatStreamEvent> {
    let response: Response;

    try {
      response = await fetch(this.endpoint, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          message: request.message,
          conversation_id: request.conversationId ?? null,
          context: request.context
            ? {
                project_id: request.context.projectId ?? null,
                view: request.context.view ?? null,
              }
            : null,
        }),
      });
    } catch {
      yield { type: "error", code: "network", message: NETWORK_ERROR };
      return;
    }

    if (!response.ok || !response.body) {
      yield { type: "error", code: "http", message: GENERIC_ERROR };
      return;
    }

    yield* this.readEvents(response.body);
  }

  /** Parsuje strumień bajtów na zdarzenia SSE (bloki rozdzielone pustą linią). */
  private async *readEvents(
    body: ReadableStream<Uint8Array>,
  ): AsyncGenerator<ChatStreamEvent> {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });

        // Zdarzenie może przyjść rozbite między porcjami — przetwarzamy
        // wyłącznie kompletne bloki, resztę zostawiamy w buforze.
        let separator = buffer.indexOf("\n\n");
        while (separator !== -1) {
          const block = buffer.slice(0, separator);
          buffer = buffer.slice(separator + 2);
          const event = this.parseBlock(block);
          if (event) {
            yield event;
          }
          separator = buffer.indexOf("\n\n");
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  private parseBlock(block: string): ChatStreamEvent | null {
    let name = "";
    let data = "";

    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) {
        name = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        data = line.slice(6).trim();
      }
    }

    if (!name || !data) {
      return null;
    }

    let payload: Record<string, string>;
    try {
      payload = JSON.parse(data);
    } catch {
      return null;
    }

    switch (name) {
      case "token":
        return { type: "token", content: payload["content"] ?? "" };
      case "done":
        return {
          type: "done",
          conversationId: payload["conversationId"] ?? "",
          content: payload["content"] ?? "",
        };
      case "error":
        return {
          type: "error",
          code: payload["code"] ?? "llm_error",
          message: payload["message"] ?? GENERIC_ERROR,
        };
      default:
        return null;
    }
  }
}
