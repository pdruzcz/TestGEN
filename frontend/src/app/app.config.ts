import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from "@angular/core";
import { provideRouter } from "@angular/router";
import {
  provideHttpClient,
  withFetch,
  withInterceptors,
  withXsrfConfiguration,
} from "@angular/common/http";
import { provideAnimationsAsync } from "@angular/platform-browser/animations/async";

import { routes } from "./app.routes";
import { authInterceptor } from "./core/interceptors/auth.interceptor";
import { snakeCaseInterceptor } from "./core/interceptors/snake-case.interceptor";
import { quotaInterceptor } from "./shared/interceptors/quota-interceptor";
import { featureLockInterceptor } from "./shared/interceptors/feature-lock-interceptor";
import { ConfigService } from "./core/services/config.service";

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(
      withFetch(),
      withInterceptors([
        authInterceptor,
        snakeCaseInterceptor,
        quotaInterceptor,
        featureLockInterceptor,
      ]),
      withXsrfConfiguration({
        cookieName: "XSRF-TOKEN",
        headerName: "X-XSRF-TOKEN",
      }),
    ),
    provideAnimationsAsync(),
    // Load system config (engine_mode) once at startup — configSignal is
    // reactive, so components reading it update when the value arrives.
    provideAppInitializer(() => {
      inject(ConfigService).loadConfig();
    }),
  ],
};
