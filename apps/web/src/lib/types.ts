/**
 * RFC 9457 Problem Details error format
 */
export interface ProblemFieldError {
  field?: string;
  message: string;
}

export interface ProblemDetails {
  type?: string;
  title: string;
  status: number;
  code?: string;
  detail?: string;
  request_id?: string;
  errors?: ProblemFieldError[];
  [key: string]: unknown;
}

export type UserRole = "requester" | "buyer" | "manager" | "admin";

export interface UserPrincipal {
  id: string;
  email: string;
  display_name: string;
  roles: UserRole[];
  department_id: string | null;
  department_name: string | null;
  approval_limit_aed: string | number;
  is_demo: boolean;
  active: boolean;
}
