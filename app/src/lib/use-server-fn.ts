/**
 * Drop-in replacement for `useServerFn` from @tanstack/react-start.
 * The Catalyst port talks to /server/api/* via fetch — there's no client/server
 * boundary to bridge, so this hook is a pass-through.
 */

export function useServerFn<T extends (...args: any[]) => any>(fn: T): T {
  return fn;
}
