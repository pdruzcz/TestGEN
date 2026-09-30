import { Component } from "@angular/core";

@Component({
  selector: "app-footer",
  standalone: true,
  template: `
    <footer class="app-footer" role="contentinfo">
      <img
        src="logo-fe.svg"
        alt="Logo FE"
        class="footer-logo footer-logo--fe"
      />
      <img
        src="logo-rp.svg"
        alt="Logo RP"
        class="footer-logo footer-logo--rp"
      />
      <img
        src="logo-ue.svg"
        alt="Logo UE"
        class="footer-logo footer-logo--ue"
      />
    </footer>
  `,
  styles: [
    `
      .app-footer {
        display: flex;
        align-items: center;
        padding: 32px 48px;
        background: #ffffff;
        border-top: 1px solid #e5e7eb;
      }
      .footer-logo {
        flex-shrink: 0;
      }
      .footer-logo--fe {
        height: 96px;
        width: auto;
      }
      .footer-logo--rp {
        height: 72px;
        width: auto;
        margin: 0 auto;
      }
      .footer-logo--ue {
        height: 96px;
        width: auto;
      }

      @media (max-width: 768px) {
        .app-footer {
          padding: 24px 16px;
          flex-wrap: wrap;
          justify-content: center;
          gap: 24px;
        }
        .footer-logo--fe {
          height: 64px;
        }
        .footer-logo--rp {
          height: 48px;
        }
        .footer-logo--ue {
          height: 64px;
        }
      }
    `,
  ],
})
export class FooterComponent {}
