import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line, ReferenceLine } from 'recharts';
import type { ReactNode } from 'react';
import { clockStr } from '../lib/engine';

const axis = { stroke: 'rgba(231,234,240,.35)', fontSize: 10.5, fontFamily: 'JetBrains Mono Variable', tickLine: false, axisLine: false };
const grid = <CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} />;
const tip = (fmt: (v: number) => string) => (
  <Tooltip cursor={{ stroke: 'rgba(255,255,255,.15)' }} contentStyle={{ background: 'rgba(10,13,19,.95)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 10, fontSize: 12 }}
    labelFormatter={v => 'T+ ' + clockStr(v as number)} formatter={(v) => fmt(v as number)} />
);

export function TimeArea({ data, k, color = '#5eead4', fmt = v => String(v), domain, height = 160, refs }: {
  data: Record<string, number>[]; k: string; color?: string; fmt?: (v: number) => string; domain?: [number, number]; height?: number; refs?: { x: number; label: string }[];
}) {
  const id = 'g' + k + color.replace('#', '');
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
        <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={color} stopOpacity={0.35} /><stop offset="1" stopColor={color} stopOpacity={0} /></linearGradient></defs>
        {grid}
        <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={clockStr} {...axis} />
        <YAxis domain={domain || ['auto', 'auto']} tickFormatter={fmt} {...axis} width={48} />
        {tip(fmt)}
        {refs?.map(r => <ReferenceLine key={r.label} x={r.x} stroke="#f87171" strokeDasharray="3 3" label={{ value: r.label, fill: '#f87171', fontSize: 10, position: 'insideTopRight' }} />)}
        <Area type="monotone" dataKey={k} stroke={color} strokeWidth={1.5} fill={`url(#${id})`} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function TimeLines({ data, lines, fmt = v => String(v), domain, height = 160 }: {
  data: Record<string, number>[]; lines: { k: string; color: string; name: string }[]; fmt?: (v: number) => string; domain?: [number, number]; height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
        {grid}
        <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={clockStr} {...axis} />
        <YAxis domain={domain || ['auto', 'auto']} tickFormatter={fmt} {...axis} width={48} />
        {tip(fmt)}
        {lines.map(l => <Line key={l.k} type="stepAfter" dataKey={l.k} name={l.name} stroke={l.color} strokeWidth={1.5} dot={false} isAnimationActive={false} />)}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function Legend({ items }: { items: { c: string; l: ReactNode }[] }) {
  return <div className="flex flex-wrap gap-3 text-[11px] text-muted">{items.map((i, k) => <span key={k} className="flex items-center gap-1.5"><i className="h-0.5 w-3 rounded" style={{ background: i.c }} />{i.l}</span>)}</div>;
}
