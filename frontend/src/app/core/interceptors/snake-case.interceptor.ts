import { HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { map } from 'rxjs/operators';

function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function camelToSnake(str: string): string {
  // Handle consecutive capitals: "testGEN" → "test_gen", "NIP" → "nip"
  return str
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1_$2')
    .replace(/([a-z\d])([A-Z])/g, '$1_$2')
    .toLowerCase();
}

function transformKeys(obj: unknown, transformFn: (key: string) => string): unknown {
  if (Array.isArray(obj)) {
    return obj.map((item) => transformKeys(item, transformFn));
  }
  if (obj !== null && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([key, value]) => [
        transformFn(key),
        transformKeys(value, transformFn),
      ]),
    );
  }
  return obj;
}

export const snakeCaseInterceptor: HttpInterceptorFn = (req, next) => {
  // Transform outgoing request body: camelCase → snake_case
  // Skip FormData, Blob, ArrayBuffer — only transform plain objects
  if (
    req.body &&
    typeof req.body === 'object' &&
    !(req.body instanceof FormData) &&
    !(req.body instanceof Blob) &&
    !(req.body instanceof ArrayBuffer)
  ) {
    const transformedBody = transformKeys(req.body, camelToSnake);
    req = req.clone({ body: transformedBody });
  }

  // Transform incoming response body: snake_case → camelCase
  return next(req).pipe(
    map((event) => {
      if (
        event instanceof HttpResponse &&
        event.body &&
        !(event.body instanceof Blob) &&
        !(event.body instanceof ArrayBuffer)
      ) {
        const transformedBody = transformKeys(event.body, snakeToCamel);
        return event.clone({ body: transformedBody });
      }
      return event;
    }),
  );
};
