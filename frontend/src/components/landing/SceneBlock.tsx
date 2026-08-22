import SceneVideo from "./SceneVideo";

export type SceneReadout = { label: string; value: string };

type Props = {
  index: string;
  kicker: string;
  title: React.ReactNode;
  body: string;
  video: string;
  videoAlt: string;
  hudLabel: string;
  readouts: SceneReadout[];
  /** Görüntü sağda mı solda mı — sahneler arası ritim için değişir. */
  flip?: boolean;
};

/**
 * Anlatı sahnesi. Her sahne bir ŞEY anlatır; dekor değildir.
 * Sol/sağ dönüşümlü yerleşim, ortalanmış üç ikon kartı yerine
 * asimetrik iki kolon + gravürlü ölçüm listesi.
 */
export default function SceneBlock({
  index,
  kicker,
  title,
  body,
  video,
  videoAlt,
  hudLabel,
  readouts,
  flip = false,
}: Props) {
  return (
    <section
      id={`sahne-${index}`}
      data-scene={index}
      className="section relative min-h-[100svh] content-center"
    >
      <div
        className={`shell grid grid-cols-12 items-center gap-x-0
                    lg:gap-x-[var(--p-space-5)]
                    gap-y-[var(--p-space-5)]`}
      >
        {/* Metin kolonu */}
        <div
          className={`col-span-12 lg:col-span-5 ${
            flip ? "lg:order-2 lg:col-start-8" : "lg:order-1"
          }`}
        >
          <div className="mb-[var(--p-space-4)] flex items-baseline gap-[var(--p-space-3)]">
            <span
              className="t-counter font-display leading-none"
              style={{ fontSize: "var(--p-display-sm)" }}
              aria-hidden="true"
            >
              {index}
            </span>
            <span className="t-dial">{kicker}</span>
          </div>

          <h2 className="t-display-sm" data-reveal>
            {title}
          </h2>

          <p
            className="t-body mt-[var(--p-space-4)]"
            data-reveal
            style={{ "--reveal-delay": "120ms" } as React.CSSProperties}
          >
            {body}
          </p>

          {/* Ölçüm listesi — noktalı ara ile, alet spec sayfası gibi */}
          <dl
            className="mt-[var(--p-space-5)] border-t border-[var(--edge-hair)]"
            data-reveal
            style={{ "--reveal-delay": "220ms" } as React.CSSProperties}
          >
            {readouts.map((r) => (
              <div
                key={r.label}
                className="flex items-baseline justify-between gap-[var(--p-space-3)]
                           border-b border-[var(--edge-hair)]
                           py-[var(--p-space-3)]"
              >
                <dt className="t-dial">{r.label}</dt>
                <dd className="t-measure">{r.value}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Görüntü kolonu */}
        <div
          className={`col-span-12 lg:col-span-6 ${
            flip ? "lg:order-1 lg:col-start-1" : "lg:order-2 lg:col-start-7"
          }`}
          data-reveal="iris"
        >
          <SceneVideo
            src={video}
            alt={videoAlt}
            hudLabel={hudLabel}
            className="aspect-video w-full"
          />
        </div>
      </div>
    </section>
  );
}
