import { TestBed } from "@angular/core/testing";
import { LlmGatewayService } from "./llm-gateway.service";

/** Buduje odpowiedź fetch ze strumieniem SSE złożonym z podanych porcji. */
function sseResponse(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, { status });
}

const TOKEN_STREAM = [
  'event: token\ndata: {"content":"Masz "}\n\n',
  'event: token\ndata: {"content":"3 luki."}\n\n',
  'event: done\ndata: {"conversationId":"c-1","content":"Masz 3 luki."}\n\n',
];

describe("LlmGatewayService", () => {
  let service: LlmGatewayService;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(LlmGatewayService);
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function collect(): Promise<unknown[]> {
    const events: unknown[] = [];
    for await (const event of service.streamMessage({ message: "Ile mam luk?" })) {
      events.push(event);
    }
    return events;
  }

  it("zwraca kolejne zdarzenia token w kolejności napływania", async () => {
    fetchMock.mockResolvedValue(sseResponse(TOKEN_STREAM));

    const events = await collect();

    expect(events.filter((e: any) => e.type === "token").map((e: any) => e.content)).toEqual([
      "Masz ",
      "3 luki.",
    ]);
  });

  it("kończy zdarzeniem done z identyfikatorem rozmowy", async () => {
    fetchMock.mockResolvedValue(sseResponse(TOKEN_STREAM));

    const events = (await collect()) as any[];

    expect(events.at(-1)).toMatchObject({ type: "done", conversationId: "c-1" });
  });

  it("skleja zdarzenie rozbite między porcjami strumienia", async () => {
    fetchMock.mockResolvedValue(
      sseResponse([
        'event: token\ndata: {"con',
        'tent":"Ala"}\n\n',
        'event: done\ndata: {"conversationId":"c-2","content":"Ala"}\n\n',
      ]),
    );

    const events = (await collect()) as any[];

    expect(events[0]).toMatchObject({ type: "token", content: "Ala" });
  });

  it("wysyła żądanie na endpoint czatu z ciasteczkami sesji", async () => {
    fetchMock.mockResolvedValue(sseResponse(TOKEN_STREAM));

    await collect();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/chat/message");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body).message).toBe("Ile mam luk?");
  });

  it("przekazuje zdarzenie error ze strumienia", async () => {
    fetchMock.mockResolvedValue(
      sseResponse([
        'event: error\ndata: {"code":"rate_limit","message":"Przekroczono limit zapytań."}\n\n',
      ]),
    );

    const events = (await collect()) as any[];

    expect(events[0]).toMatchObject({ type: "error", code: "rate_limit" });
  });

  it("zamienia błąd HTTP na zdarzenie error po polsku", async () => {
    fetchMock.mockResolvedValue(sseResponse([], 500));

    const events = (await collect()) as any[];

    expect(events[0].type).toBe("error");
    expect(events[0].message).toMatch(/asystent|odpowiedz/i);
  });

  it("zamienia błąd sieci na zdarzenie error", async () => {
    fetchMock.mockRejectedValue(new TypeError("network down"));

    const events = (await collect()) as any[];

    expect(events[0]).toMatchObject({ type: "error", code: "network" });
  });

  it("ignoruje puste linie i komentarze SSE", async () => {
    fetchMock.mockResolvedValue(
      sseResponse([
        ": keep-alive\n\n",
        'event: token\ndata: {"content":"ok"}\n\n',
        'event: done\ndata: {"conversationId":"c-3","content":"ok"}\n\n',
      ]),
    );

    const events = (await collect()) as any[];

    expect(events).toHaveLength(2);
  });
});
