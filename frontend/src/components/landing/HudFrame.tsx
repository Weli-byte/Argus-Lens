/**
 * Video/canvas üstündeki ölçüm çerçevesi — vizör köşe işaretleri.
 * Dekor değil: kadrajın nerede bittiğini gösterir, cyan burada izinli
 * çünkü ölçüm katmanına ait.
 */
const TICK = "absolute bg-[var(--hud-tick)]";

export default function HudFrame({ label }: { label?: string }) {
  return (
    <div className="hud-frame" aria-hidden="true">
      {/* Sol üst */}
      <span className={`${TICK} left-0 top-0 h-px w-[var(--p-space-5)]`} />
      <span className={`${TICK} left-0 top-0 h-[var(--p-space-5)] w-px`} />
      {/* Sağ üst */}
      <span className={`${TICK} right-0 top-0 h-px w-[var(--p-space-5)]`} />
      <span className={`${TICK} right-0 top-0 h-[var(--p-space-5)] w-px`} />
      {/* Sol alt */}
      <span className={`${TICK} bottom-0 left-0 h-px w-[var(--p-space-5)]`} />
      <span className={`${TICK} bottom-0 left-0 h-[var(--p-space-5)] w-px`} />
      {/* Sağ alt */}
      <span className={`${TICK} bottom-0 right-0 h-px w-[var(--p-space-5)]`} />
      <span className={`${TICK} bottom-0 right-0 h-[var(--p-space-5)] w-px`} />

      {/* Merkez nişangâh — diyafram ekseni */}
      <span className={`${TICK} left-1/2 top-1/2 h-px w-[var(--p-space-4)] -translate-x-1/2 opacity-40`} />
      <span className={`${TICK} left-1/2 top-1/2 h-[var(--p-space-4)] w-px -translate-y-1/2 opacity-40`} />

      {label ? (
        <span className="t-measure absolute left-[var(--p-space-4)] top-[var(--p-space-3)]">
          {label}
        </span>
      ) : null}
    </div>
  );
}
