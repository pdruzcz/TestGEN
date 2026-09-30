import { Component, output, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";

export type DastAuthType = "none" | "form" | "token" | "basic";

export interface DastLaunchConfig {
  targetUrl: string;
  authConfig: Record<string, string> | null;
}

/**
 * Story 4.6: collects the target URL and optional authentication for a DAST
 * (OWASP ZAP) scan and emits the launch configuration. Authentication fields are
 * shown conditionally based on the selected auth type.
 */
@Component({
  selector: "app-dast-config",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
  ],
  templateUrl: "./dast-config.component.html",
  styleUrls: ["./dast-config.component.scss"],
})
export class DastConfigComponent {
  readonly launch = output<DastLaunchConfig>();

  readonly targetUrl = signal("");
  readonly authType = signal<DastAuthType>("none");
  readonly loginUrl = signal("");
  readonly username = signal("");
  readonly password = signal("");
  readonly token = signal("");

  canLaunch(): boolean {
    return /^https?:\/\/.+/.test(this.targetUrl().trim());
  }

  onLaunch(): void {
    if (!this.canLaunch()) return;
    this.launch.emit({
      targetUrl: this.targetUrl().trim(),
      authConfig: this.buildAuthConfig(),
    });
  }

  private buildAuthConfig(): Record<string, string> | null {
    const type = this.authType();
    if (type === "none") return null;
    if (type === "token") {
      return { auth_type: "token", token: this.token() };
    }
    if (type === "basic") {
      return {
        auth_type: "basic",
        username: this.username(),
        password: this.password(),
      };
    }
    return {
      auth_type: "form",
      login_url: this.loginUrl(),
      username: this.username(),
      password: this.password(),
    };
  }
}
