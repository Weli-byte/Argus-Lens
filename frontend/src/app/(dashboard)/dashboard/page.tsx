import { redirect } from "next/navigation";

/**
 * `/dashboard` tanıtım ekranı kaldırıldı.
 *
 * Konsola giren operatörün ilk gördüğü şey pazarlama panelleri değil,
 * çalışan kamera akışı olmalı. Rota canlı görüntüye yönlenir; eski
 * sinematik paneller landing sayfasında zaten anlatılıyor.
 */
export default function DashboardIndex() {
  redirect("/dashboard/vision");
}
