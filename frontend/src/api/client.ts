export interface ApiValidationIssue {
  loc?: Array<string | number>
  msg?: string
  type?: string
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number | null,
    public readonly validationIssues: ApiValidationIssue[] = [],
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined
export const API_BASE_URL = (configuredBaseUrl ?? 'http://localhost:8000').replace(/\/$/, '')

function readableDetail(value: unknown): {
  message: string
  validationIssues: ApiValidationIssue[]
} {
  if (typeof value === 'string') {
    return { message: value, validationIssues: [] }
  }
  if (Array.isArray(value)) {
    const issues = value.filter((item): item is ApiValidationIssue => {
      return typeof item === 'object' && item !== null
    })
    return { message: 'Please correct the highlighted request fields.', validationIssues: issues }
  }
  return { message: 'The backend rejected this request.', validationIssues: [] }
}

function hasDetail(value: unknown): value is { detail: unknown } {
  return typeof value === 'object' && value !== null && 'detail' in value
}

export async function requestJson<T>(
  path: string,
  options: RequestInit,
  validate: (value: unknown) => value is T,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
    })
  } catch {
    throw new ApiError('Cannot reach AlphaPilot backend.', null)
  }

  let body: unknown
  try {
    body = await response.json()
  } catch {
    body = null
  }

  if (!response.ok) {
    const detail = hasDetail(body)
      ? readableDetail(body.detail)
      : { message: 'AlphaPilot backend returned an unexpected error.', validationIssues: [] }
    throw new ApiError(detail.message, response.status, detail.validationIssues)
  }

  if (!validate(body)) {
    throw new ApiError('AlphaPilot backend returned an invalid response.', response.status)
  }
  return body
}
