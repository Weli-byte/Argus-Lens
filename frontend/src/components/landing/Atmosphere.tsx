/**
 * Katmanlı atmosferik arka plan — yön A "Optik Enstrüman".
 * Beş sabit katman, hepsi pointer-events:none, hepsi token'lardan beslenir.
 * Server component: ilk boya için JS maliyeti sıfır.
 *
 *  L1 optic-flare     kaplama parlamaları (üç ayrı optik hayalet)
 *  L2 optic-rules     kazınmış yatay taksimat (alet kadranı)
 *  L3 optic-streak    anamorfik çizgi (scroll ile kayar — SceneChoreography)
 *  L4 optic-vignette  optik vinyet
 *  L5 optic-grain     35mm grain
 */
export default function Atmosphere() {
  return (
    <div aria-hidden="true">
      <div className="optic-flare" />
      <div className="optic-rules" />
      <div className="optic-streak" data-streak />
      <div className="optic-vignette" />
      <div className="optic-grain" />
    </div>
  );
}
