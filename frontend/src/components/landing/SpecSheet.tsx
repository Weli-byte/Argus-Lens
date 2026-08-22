const SPECS: Array<[string, string, string]> = [
  ["Optik hat", "Çözünürlük", "1280 × 720 · 60 fps"],
  ["Optik hat", "Gecikme (uçtan uca)", "24 ms"],
  ["Tespit", "Model", "GroundingDINO · zero-shot"],
  ["Tespit", "Eşzamanlı nesne", "128 / kare"],
  ["Zamansal", "Ufuk", "Temporal Transformer · 90 sn"],
  ["Zamansal", "Anomali eşiği", "σ > 2.4"],
  ["Vital", "Kanal", "Nabız · SpO₂ · Göz içi basınç"],
  ["Vital", "Örnekleme", "4 Hz"],
  ["Altyapı", "Çalışma", "CUDA FP16 · batch scheduler"],
  ["Altyapı", "Yetki", "JWT · RBAC · rate limit"],
];

/**
 * Teknik künye. Üç ortalanmış ikon kartı değil — alet kataloğu tablosu.
 * Gruplar sol sütunda tek kez yazılır, satırlar gravür çizgisiyle ayrılır.
 */
export default function SpecSheet() {
  return (
    <section id="kunye" className="section">
      <div className="shell">
        <div className="mb-[var(--p-space-5)] flex items-end justify-between gap-[var(--p-space-4)]">
          <h2 className="t-display-sm" data-reveal>
            TEKNİK <span className="t-counter">künye</span>
          </h2>
          <span className="t-dial hidden sm:block">Rev. 4 · 2026</span>
        </div>

        <table className="w-full border-collapse text-left">
          <caption className="visually-hidden">
            ArgusLens platformunun teknik özellikleri
          </caption>
          <thead className="visually-hidden">
            <tr>
              <th scope="col">Katman</th>
              <th scope="col">Özellik</th>
              <th scope="col">Değer</th>
            </tr>
          </thead>
          <tbody>
            {SPECS.map(([group, key, value], i) => {
              const firstOfGroup = i === 0 || SPECS[i - 1][0] !== group;
              return (
                <tr
                  key={`${group}-${key}`}
                  className="border-t border-[var(--edge-hair)]"
                  data-reveal
                  style={
                    { "--reveal-delay": `${i * 35}ms` } as React.CSSProperties
                  }
                >
                  <td className="t-dial w-[26%] py-[var(--p-space-3)] align-baseline">
                    {firstOfGroup ? group : ""}
                  </td>
                  <td className="t-body w-[42%] py-[var(--p-space-3)] align-baseline">
                    {key}
                  </td>
                  <td className="t-measure py-[var(--p-space-3)] text-right align-baseline">
                    {value}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
