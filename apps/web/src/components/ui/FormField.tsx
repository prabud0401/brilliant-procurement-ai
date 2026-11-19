import React, { useId } from "react";

export interface FormFieldProps {
  label: string;
  error?: string | null;
  helperText?: string;
  required?: boolean;
  htmlFor?: string;
  children: React.ReactNode;
  className?: string;
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  error,
  helperText,
  required = false,
  htmlFor,
  children,
  className = "",
}) => {
  const generatedId = useId();
  const inputId = htmlFor || generatedId;
  const errorId = `${inputId}-error`;
  const helperId = `${inputId}-helper`;

  return (
    <div className={`space-y-1.5 ${className}`}>
      <label
        htmlFor={inputId}
        className="block text-sm font-medium text-slate-700"
      >
        {label}
        {required && (
          <span className="ml-1 text-rose-500" aria-hidden="true">
            *
          </span>
        )}
      </label>

      {/* Render children (e.g. input/select) */}
      <div>{children}</div>

      {helperText && !error && (
        <p id={helperId} className="text-xs text-slate-500">
          {helperText}
        </p>
      )}

      {error && (
        <p id={errorId} className="text-xs font-medium text-rose-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
};

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className = "", error, ...props }, ref) => {
    const errorClasses = error
      ? "border-rose-300 text-rose-900 placeholder-rose-300 focus:border-rose-500 focus:ring-rose-500"
      : "border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:ring-blue-500";

    return (
      <input
        ref={ref}
        className={`block w-full rounded-md border px-3 py-2 text-sm shadow-sm transition duration-150 ease-in-out focus:outline-none focus:ring-1 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 ${errorClasses} ${className}`}
        aria-invalid={error ? "true" : "false"}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  error?: boolean;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className = "", error, children, ...props }, ref) => {
    const errorClasses = error
      ? "border-rose-300 text-rose-900 focus:border-rose-500 focus:ring-rose-500"
      : "border-slate-300 text-slate-900 focus:border-blue-500 focus:ring-blue-500";

    return (
      <select
        ref={ref}
        className={`block w-full rounded-md border bg-white px-3 py-2 text-sm shadow-sm transition duration-150 ease-in-out focus:outline-none focus:ring-1 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 ${errorClasses} ${className}`}
        aria-invalid={error ? "true" : "false"}
        {...props}
      >
        {children}
      </select>
    );
  }
);
Select.displayName = "Select";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className = "", error, ...props }, ref) => {
    const errorClasses = error
      ? "border-rose-300 text-rose-900 placeholder-rose-300 focus:border-rose-500 focus:ring-rose-500"
      : "border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:ring-blue-500";

    return (
      <textarea
        ref={ref}
        className={`block w-full rounded-md border px-3 py-2 text-sm shadow-sm transition duration-150 ease-in-out focus:outline-none focus:ring-1 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 ${errorClasses} ${className}`}
        aria-invalid={error ? "true" : "false"}
        {...props}
      />
    );
  }
);
Textarea.displayName = "Textarea";
