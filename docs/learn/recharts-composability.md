# Recharts composability

Sentinel's dashboard uses Recharts to visualize trace volume and spend.
Recharts' API is unusual: charts are composed of nested React components,
not configured via an options object. That's what makes them feel
declarative.

```tsx
<ResponsiveContainer width="100%" height={240}>
  <LineChart data={data}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="ts" />
    <YAxis />
    <Tooltip />
    <Line type="monotone" dataKey="cost_usd" stroke="#10b981" />
  </LineChart>
</ResponsiveContainer>
```

## Why ResponsiveContainer

Charts need a fixed pixel size to render. `ResponsiveContainer` measures
its parent and forwards the dimensions. Without it, charts render at 0×0
in a flex container.

## Composability tradeoffs

- **Pros**: easy to wire interactivity (`onClick` on a `<Bar>` propagates
  the datum), easy to slot custom tooltips.
- **Cons**: hard to share config across charts. A "Sentinel chart" theme
  has to live in a wrapper component, not a config object.

## SVG, not Canvas

Recharts renders to SVG. Great for crispness; bad if you have thousands of
points (one DOM node per point). For Sentinel's traffic-volume bins,
we aggregate to ≤120 buckets server-side before sending to the dashboard.
