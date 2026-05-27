# React server components vs. client components

Next.js 13+ defaults every component to a *Server Component*. They render
on the server, send HTML to the browser, and never ship their JS bundle.
Client Components — marked by `"use client"` at the top of the file —
render on the server *and* hydrate in the browser, where they regain
state, effects, and event handlers.

## When Sentinel uses each

- **Server**: any page that just fetches and renders (e.g., a static
  layout). Sentinel uses these sparingly.
- **Client**: every page that needs `useState`, `useEffect`, or
  `usePathname`. That's most of our dashboard (traces, verifications,
  policies, evals) because they fetch from the gateway on the client and
  poll for updates.

## The cost

Client components ship JS to every visitor. For a dashboard this is fine
(users are interactive anyway). For a marketing page it would be a
regression.

## The gotcha

You cannot pass a function from a server component as a prop to a client
component, because functions aren't serializable. If you need a callback,
either lift state into a client parent or use a server action.
