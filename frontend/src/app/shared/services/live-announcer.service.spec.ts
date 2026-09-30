import { LiveAnnouncer } from "@angular/cdk/a11y";
import { TestBed } from "@angular/core/testing";
import type { Mock } from "vitest";
import { LiveAnnouncerService } from "./live-announcer.service";

describe("LiveAnnouncerService", () => {
  let service: LiveAnnouncerService;
  let cdkAnnouncer: { announce: Mock; clear: Mock };

  beforeEach(() => {
    cdkAnnouncer = {
      announce: vi.fn().mockResolvedValue(undefined),
      clear: vi.fn(),
    };
    TestBed.configureTestingModule({
      providers: [{ provide: LiveAnnouncer, useValue: cdkAnnouncer }],
    });
    service = TestBed.inject(LiveAnnouncerService);
  });

  it("announce domyślnie używa polite (AC3)", async () => {
    await service.announce("Analiza zakończona");
    expect(cdkAnnouncer.announce).toHaveBeenCalledWith(
      "Analiza zakończona",
      "polite",
    );
  });

  it("announce przekazuje priorytet assertive (AC3)", async () => {
    await service.announce("Błąd zapisu", "assertive");
    expect(cdkAnnouncer.announce).toHaveBeenCalledWith(
      "Błąd zapisu",
      "assertive",
    );
  });

  it("announceError używa assertive (AC3)", async () => {
    await service.announceError("Eksport nie powiódł się");
    expect(cdkAnnouncer.announce).toHaveBeenCalledWith(
      "Eksport nie powiódł się",
      "assertive",
    );
  });

  it("clear deleguje do CDK LiveAnnouncer", () => {
    service.clear();
    expect(cdkAnnouncer.clear).toHaveBeenCalled();
  });
});
