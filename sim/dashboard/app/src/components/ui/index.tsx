import * as RT from '@radix-ui/react-tooltip';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { ReactNode, ButtonHTMLAttributes, CSSProperties } from 'react';

export const cn = (...a: ClassValue[]) => twMerge(clsx(a));

export function Panel({ title, sub, actions, explain, className, bodyClass, children, id, style }: {
  title?: ReactNode; sub?: ReactNode; actions?: ReactNode; explain?: string; className?: string; bodyClass?: string; children: ReactNode; id?: string; style?: CSSProperties;
}) {
  return (
    <section id={id} data-explain={explain} style={style} className={cn('glass flex min-h-0 flex-col overflow-hidden', className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-white/[0.045] bg-white/[0.012] px-4.5 py-3">
          <div className="min-w-0">
            {title && <h3 className="text-[13px] font-semibold tracking-tight text-hi">{title}</h3>}
            {sub && <p className="mt-0.5 truncate text-[11.5px] text-muted">{sub}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
        </header>
      )}
      <div className={cn('min-h-0 flex-1 p-4.5', bodyClass)}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, sub, tone, className }: { label: ReactNode; value: ReactNode; sub?: ReactNode; tone?: string; className?: string }) {
  return (
    <div className={cn('min-w-0', className)}>
      <div className="eyebrow">{label}</div>
      <div className="num mt-1 text-[28px] leading-tight font-medium tracking-tight text-hi" style={tone ? { color: tone } : undefined}>{value}</div>
      {sub && <div className="mt-1.5 truncate text-xs text-muted">{sub}</div>}
    </div>
  );
}

export function Chip({ children, color, className, title }: { children: ReactNode; color?: string; className?: string; title?: string }) {
  return (
    <span title={title} className={cn('inline-flex items-center gap-1.5 rounded-md border border-current/15 px-2 py-0.5 text-[11px] font-medium whitespace-nowrap shadow-xs', className)}
      style={{ color: color || 'var(--muted)', background: color ? `color-mix(in srgb, ${color} 12%, transparent)` : 'rgb(255 255 255 / 0.05)' }}>
      {children}
    </span>
  );
}

export function Dot({ color, pulse, size = 8 }: { color: string; pulse?: boolean; size?: number }) {
  return (
    <span className="relative inline-flex shrink-0" style={{ width: size, height: size }}>
      {pulse && <span className="ping absolute inset-0 rounded-full opacity-75" style={{ background: color }} />}
      <span className="relative inline-flex rounded-full shadow-xs" style={{ width: size, height: size, background: color }} />
    </span>
  );
}

export function Button({ className, variant = 'ghost', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'ghost' | 'solid' | 'accent' }) {
  return (
    <button {...p} className={cn(
      'inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-[12.5px] font-medium transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-accent/60 active:scale-[0.98] disabled:opacity-40 cursor-pointer',
      variant === 'ghost' && 'text-muted hover:bg-white/[.06] hover:text-hi',
      variant === 'solid' && 'border border-line bg-white/[.05] text-fg shadow-xs hover:border-line-hi hover:bg-white/[.09] hover:text-hi',
      variant === 'accent' && 'bg-accent font-semibold text-[#03221d] shadow-sm shadow-accent/25 hover:brightness-105 active:brightness-95',
      className)} />
  );
}

export function Segmented<T extends string>({ value, options, onChange, className }: { value: T; options: { v: T; l: ReactNode }[]; onChange: (v: T) => void; className?: string }) {
  return (
    <div role="tablist" className={cn('inline-flex rounded-lg border border-line bg-black/40 p-0.5 shadow-inner backdrop-blur-sm', className)}>
      {options.map(o => (
        <button key={o.v} role="tab" aria-selected={o.v === value} onClick={() => onChange(o.v)}
          className={cn('h-6 rounded-md px-2.5 text-xs font-medium transition-all duration-150 cursor-pointer',
            o.v === value ? 'bg-white/[.12] text-hi shadow-xs' : 'text-muted hover:text-fg hover:bg-white/[.03]')}>
          {o.l}
        </button>
      ))}
    </div>
  );
}

export function Bar({ v, color = 'var(--accent)', className }: { v: number; color?: string; className?: string }) {
  return (
    <div className={cn('h-1.5 w-full overflow-hidden rounded-full bg-white/[.07] shadow-inner', className)}>
      <div className="h-full rounded-full transition-[width] duration-500 ease-out" style={{ width: Math.max(0, Math.min(100, v * 100)) + '%', background: color }} />
    </div>
  );
}

export function Tip({ children, content }: { children: ReactNode; content: ReactNode }) {
  return (
    <RT.Root delayDuration={200}>
      <RT.Trigger asChild>{children}</RT.Trigger>
      <RT.Portal>
        <RT.Content sideOffset={6} className="z-50 max-w-xs rounded-lg border border-line bg-[#0b0e14]/95 px-2.5 py-1.5 text-xs text-fg shadow-xl backdrop-blur">
          {content}
        </RT.Content>
      </RT.Portal>
    </RT.Root>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="flex h-full min-h-20 items-center justify-center px-6 text-center text-[13px] text-faint">{children}</div>;
}
