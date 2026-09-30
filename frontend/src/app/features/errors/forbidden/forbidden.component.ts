import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-forbidden',
  standalone: true,
  imports: [RouterLink],
  template: `
    <main class="error-page" role="alert" id="main-content" tabindex="-1">
      <h1>403 — Brak uprawnień</h1>
      <p>Nie masz uprawnień do wyświetlenia tej strony.</p>
      <a routerLink="/settings/profile">Wróć do profilu</a>
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
export class ForbiddenComponent {}
