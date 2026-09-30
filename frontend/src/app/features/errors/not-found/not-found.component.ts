import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-not-found',
  standalone: true,
  imports: [RouterLink],
  template: `
    <main class="error-page" role="alert" id="main-content" tabindex="-1">
      <h1>404 — Nie znaleziono</h1>
      <p>Strona, której szukasz, nie istnieje.</p>
      <a routerLink="/">Wróć na stronę główną</a>
    </main>
  `,
  styles: [
    `
      .error-page {
        text-align: center;
        padding: 3rem;
      }
    `,
  ],
})
export class NotFoundComponent {}
