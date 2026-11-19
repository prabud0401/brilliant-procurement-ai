import Link from "next/link";
import { FileQuestion, Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-200/80 text-slate-600">
        <FileQuestion className="h-8 w-8" aria-hidden="true" />
      </div>
      <h1 className="mt-6 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
        Page Not Found
      </h1>
      <p className="mt-2 max-w-md text-sm text-slate-600">
        The page you are looking for does not exist or may have been moved.
      </p>

      <div className="mt-8">
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          <Home className="h-4 w-4" aria-hidden="true" />
          Return to Home
        </Link>
      </div>
    </div>
  );
}
