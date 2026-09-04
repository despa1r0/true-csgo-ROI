import type { ApiErrorBody } from "./types";

type QueryValue = string | number | boolean | null | undefined;

export type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  query?: Record<string, QueryValue>;
};

export class ApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody | null;
  readonly url: string;

  constructor(message: string, status: number, url: string, body: ApiErrorBody | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.url = url;
    this.body = body;
  }
}

function buildUrl(path: string, query?: Record<string, QueryValue>) {
  const url = new URL(path, window.location.origin);

  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });

  return `${url.pathname}${url.search}`;
}

async function parseResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text || null;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, query, ...requestInit } = options;
  const url = buildUrl(path, query);
  const hasJsonBody = body !== undefined && !(body instanceof FormData);
  const response = await fetch(url, {
    ...requestInit,
    body: body === undefined ? undefined : hasJsonBody ? JSON.stringify(body) : (body as BodyInit),
    headers: {
      Accept: "application/json",
      ...(hasJsonBody ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  });
  const responseBody = await parseResponseBody(response);

  if (!response.ok) {
    const errorBody =
      responseBody && typeof responseBody === "object" ? (responseBody as ApiErrorBody) : null;
    const detail = typeof errorBody?.detail === "string" ? errorBody.detail : null;
    throw new ApiError(detail ?? response.statusText ?? "API request failed", response.status, url, errorBody);
  }

  return responseBody as T;
}

export const apiClient = {
  get<T>(path: string, options?: Omit<RequestOptions, "body" | "method">) {
    return apiRequest<T>(path, { ...options, method: "GET" });
  },
  post<TResponse, TBody = unknown>(
    path: string,
    body: TBody,
    options?: Omit<RequestOptions, "body" | "method">,
  ) {
    return apiRequest<TResponse>(path, { ...options, body, method: "POST" });
  },
};
