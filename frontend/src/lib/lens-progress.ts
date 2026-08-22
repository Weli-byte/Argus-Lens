/**
 * 3D mercek yığını ile scroll koreografisi arasındaki tek yönlü kanal.
 *
 * GSAP ScrollTrigger buraya yazar, useFrame buradan okur.
 * React state kullanılmaz: kare başına re-render olmaz.
 */
export const lensProgress = {
  /** 0 → 1, hero sahnesi boyunca odak dalışı */
  value: 0,
  /** İmleç paralaksı, -1 → 1 */
  px: 0,
  py: 0,
};
