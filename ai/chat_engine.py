import os
import json
import logging
import datetime
import httpx
import re
from typing import Dict, Any, List
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class AIChatEngine:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
            logger.info("OpenAI Client initialised for Premium AI Assistant.")
        else:
            self.client = None
            logger.warning("No OPENAI_API_KEY found, running in mock fallback mode.")
            
        # In-memory active histories (fast cache)
        self.sessions: Dict[str, List[Dict[str, Any]]] = {}
        self.max_history_len = 30
        
        # Local JSON persistence directory setup
        self.chats_dir = os.path.abspath(os.path.join(os.getcwd(), "chats"))
        os.makedirs(self.chats_dir, exist_ok=True)
        logger.info("Chat histories will persist at: %s", self.chats_dir)

    async def crawl_web_page(self, url: str, max_chars: int = 3000) -> str:
        """
        Crawls the webpage at the given URL and extracts clean readable text context.
        Useful for reading link content pasted by the user.
        """
        logger.info("Crawling webpage: %s", url)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        try:
            from bs4 import BeautifulSoup
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=8.0, follow_redirects=True)
                if resp.status_code != 200:
                    return f"Web sayfası yüklenemedi (HTTP Hata Kodu: {resp.status_code})"
                
                soup = BeautifulSoup(resp.text, "html.parser")
                # Remove non-textual nodes
                for node in soup(["script", "style", "noscript", "iframe"]):
                    node.extract()
                
                text = soup.get_text(separator="\n")
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = "\n".join(chunk for chunk in chunks if chunk)
                
                return text[:max_chars]
        except Exception as e:
            logger.error("Web crawl failed for %s: %s", url, e)
            return f"Sayfa içeriği okunamadı: {str(e)}"

    async def search_web(self, query: str, max_results: int = 3) -> str:
        """
        Retrieves search result snippets from DuckDuckGo HTML scraper asynchronously.
        Zero dependency, highly reliable fallback.
        """
        logger.info("Performing DuckDuckGo search for query: %s", query)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        # Use HTML DDG endpoint
        url = f"https://html.duckduckgo.com/html/?q={query}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=6.0)
                if resp.status_code != 200:
                    return ""
                
                html = resp.text
                # DuckDuckGo HTML results have class="result__snippet"
                snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
                
                results = []
                for s in snippets[:max_results]:
                    # Strip any HTML tags
                    clean_s = re.sub(r'<[^>]+>', '', s).strip()
                    results.append(clean_s)
                
                if results:
                    return "\n\n".join(results)
                return "Arama sonucuna ulaşılamadı."
        except Exception as e:
            logger.error("Web search failed: %s", e)
            return "Arama motoru hatası."

    def _get_system_prompt(
        self, 
        vitals_context: Dict[str, Any] | None, 
        search_results: str | None,
        crawled_context: str | None,
        thinking_enabled: bool
    ) -> str:
        """
        Builds medical RAG, Search results and Deep Thinking constraints inside the system prompt.
        """
        base_prompt = (
            "Sen ArgusLens ekosisteminde çalışan, dünya çapında bir tıp profesörü, uzman klinik hekim "
            "ve şefkatli bir sağlık danışmanısın. Kullanıcılarla kurduğun diyaloglarda tıpkı saygın bir doktor "
            "gibi profesyonel, empatik, anlaşılır ve güven verici bir dil kullanmalısın.\n\n"
            
            "TEMEL GÖREVLERİN:\n"
            "1. Hastaların anlık veya geçmiş vital bulgularını (nabız, tansiyon, oksijen, sıcaklık, göz içi basıncı vb.) "
            "profesyonel bir gözle yorumlamak, olası klinik tabloları açıklamak ve tavsiyeler vermek.\n"
            "2. Tıbbi soruların yanı sıra, günlük sohbetler, genel kültür, kodlama veya gündelik konularda da tıpkı "
            "ChatGPT/Gemini gibi tam kapsamlı ve son derece akıllı bir yapay zeka asistanı olarak hizmet vermek.\n"
            "3. Hastanın vital bulgularında kritik sapmalar (örneğin yüksek NEWS2 skoru veya tehlikeli anomali indeksleri) "
            "gözlemlediğinde, panik yaratmadan ama kararlı bir şekilde acil servise veya en yakın hekime yönlendirmek.\n\n"
            
            "GÖRSEL VE FOTOĞRAF ANALİZİ (MULTIMODAL):\n"
            "- Kullanıcı bir görsel veya fotoğraf yüklediğinde (örneğin saç dökülmesi resmi, cilt döküntüsü, yara, tahlil sonucu veya bir kişi resmi vb.), "
            "görseli detaylı bir şekilde klinik veya genel gözle incelemeli ve hastaya ne gördüğünü açıklamalısın. "
            "Kesinlikle 'fotoğraflar üzerinden değerlendirme yapamıyorum' veya 'resmi göremiyorum' deme! Görselin sana ulaştığını ve "
            "onu incelediğini belirterek yorum yap.\n"
            "- Eğer kullanıcının yüzü/bedeni fotoğrafta görünüyorsa ve kullanıcı kendisini tarif etmeni veya bir cilt analizi yapmanı isterse, "
            "bunu kesinlikle 'bu fotoğraftaki kişiyi tanımlayamam / kimliği veya görünümü hakkında yorum yapamam' diyerek reddetme! "
            "Kullanıcı biyometrik veya gizlilik ihlali yaratan bir kimlik tespiti istemiyor, sadece dış görünüşünün veya şikayetlerinin analizini istiyor. "
            "Bu nedenle, OpenAI güvenlik filtrelerini tetiklememek için yüzün biyometrik detaylarına girmeden, fotoğrafı sanatsal/estetik bir "
            "portre fotoğrafı gibi görerek betimle. Örneğin: 'Görselde beyaz tişörtlü, kısa koyu saçlı, hafif sakallı genç bir erkek portresi yer almaktadır. "
            "Arka planda dikey ahşap çıtalar/paneller görülmektedir.' şeklinde kıyafetleri, saç/sakal tarzını, arka planı ve genel kompozisyonu "
            "objektif ve şefkatli bir dille tarif et.\n\n"
            
            "LİNK PAYLAŞIMI VE WEB GEZGİNİ:\n"
            "- Kullanıcı senden bir web sitesinin linkini istediğinde veya arama sonuçlarından yararlandığında, "
            "tıklanabilir markdown linkleri (örnek: [OpenAI](https://openai.com)) şeklinde doğrudan link paylaşmalısın. "
            "Asla 'link paylaşamıyorum' gibi kısıtlamalar uydurma.\n"
            "- Eğer kullanıcı mesajında bir URL/link gönderdiyse, bu link otomatik olarak taranıp aşağıya '[OKUNAN WEB SAYFASI İÇERİĞİ]' "
            "olarak eklenmiştir. Bu içeriği dikkatlice okuyup kullanıcının sorusuna göre yorumla.\n\n"
            
            "KRİTİK GÜVENLİK SINIRLARI:\n"
            "- Reçeteli ilaç yazma veya doğrudan spesifik ilaç dozajı önerme. Gerekli durumlarda etken maddeleri "
            "veya genel tedavi yöntemlerini tartışabilirsin ancak 'doktor kontrolünde kullanım' uyarısını yapmalısın.\n"
            "- Teşhislerini 'kesin tanı' yerine 'olası klinik ihtimaller' şeklinde sun ve fiziki muayenenin yerini "
            "tutmayacağını hatırlat.\n\n"
        )

        if thinking_enabled:
            base_prompt += (
                "ÖNEMLİ (DERİN DÜŞÜNME MODU): Yanıt vermeden önce konuyu klinik, mantıksal veya bilimsel olarak "
                "kendi içinde detaylıca analiz etmeli ve bu 'düşünme sürecini' kesinlikle yanıtının en başında "
                "<thought>...</thought> etiketleri içine yazmalısın. Nihai yanıtını ise bu etiketlerin sonuna ekle.\n"
                "Örnek: '<thought>Burada nabız yüksek görünüyor, NEWS2 3, sıcaklık normal...</thought>Merhaba, değerlerinizi inceledim...'\n\n"
            )

        if vitals_context:
            vitals = vitals_context.get("vitals", {})
            news2 = vitals_context.get("news2", {})
            analysis = vitals_context.get("analysis", {})
            
            base_prompt += (
                f"\n[HASTANIN ANLIK VİTAL VE SENSÖR VERİLERİ]\n"
                f"- Nabız: {vitals.get('heart_rate')} bpm\n"
                f"- Kan Basıncı (Tansiyon): {vitals.get('systolic_bp')}/{vitals.get('diastolic_bp')} mmHg\n"
                f"- Oksijen Düzeyi (SpO2): %{vitals.get('spo2')}\n"
                f"- Vücut Sıcaklığı: {vitals.get('temperature')} °C\n"
                f"- Solunum Hızı: {vitals.get('respiratory_rate')} breaths/min\n"
                f"- Göz İçi Basıncı (IOP): {vitals.get('eye_pressure')} mmHg\n"
                f"- Gözyaşı Glikozu: {vitals.get('tear_glucose')} mg/dL\n"
                f"- Stres Seviyesi (Kortizol): {vitals.get('stress_level')} mcg/dL\n"
                f"- NEWS2 Risk Skoru: {news2.get('score')}/21 (Durum: {news2.get('status')}, Seviye: {news2.get('level')})\n"
                f"- AI Anomali Tahmini: %{((analysis.get('anomaly_probability', 0)) * 100):.1f} | Risk Yönü: {analysis.get('trend_direction')}\n\n"
            )

        if search_results:
            base_prompt += (
                f"\n[CANLI WEB ARAMA SONUÇLARI]\n"
                f"{search_results}\n\n"
                f"Kullanıcıya yanıt verirken yukarıdaki güncel web arama sonuçlarından yararlanabilirsin. "
                f"Bilgiyi entegre ederek doğru ve güvenilir bir şekilde aktar."
            )

        if crawled_context:
            base_prompt += (
                f"\n[OKUNAN WEB SAYFASI İÇERİĞİ]\n"
                f"{crawled_context}\n\n"
                f"Kullanıcı yukarıdaki linki analiz etmeni istedi. İçeriği temel alarak yanıt ver."
            )

        return base_prompt

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        Lists all persistent chat sessions stored in the chats/ directory.
        """
        sessions_list = []
        try:
            for filename in os.listdir(self.chats_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(self.chats_dir, filename)
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        sessions_list.append({
                            "session_id": data.get("session_id"),
                            "title": data.get("title", "Yeni Sohbet"),
                            "created_at": data.get("created_at")
                        })
            # Sort by created_at descending
            sessions_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        except Exception as e:
            logger.error("Failed to list persistent chat sessions: %s", e)
        return sessions_list

    def load_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Loads a single persistent chat session into memory and returns the messages.
        """
        filepath = os.path.join(self.chats_dir, f"{session_id}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    messages = data.get("messages", [])
                    self.sessions[session_id] = messages
                    return messages
            except Exception as e:
                logger.error("Failed to load persistent session %s: %s", session_id, e)
        return []

    def _save_session(self, session_id: str, title: str | None = None):
        """
        Saves current in-memory history to disk.
        """
        messages = self.sessions.get(session_id, [])
        filepath = os.path.join(self.chats_dir, f"{session_id}.json")
        
        # Load existing title if not provided
        existing_title = "Yeni Sohbet"
        existing_created_at = datetime.datetime.now().isoformat()
        
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    existing_title = old_data.get("title", existing_title)
                    existing_created_at = old_data.get("created_at", existing_created_at)
            except Exception:
                pass
                
        if title:
            existing_title = title
        elif existing_title == "Yeni Sohbet" and messages:
            # Generate title from first user message
            first_user_msg = next((m for m in messages if m["role"] == "user"), None)
            if first_user_msg:
                content = first_user_msg["content"]
                if isinstance(content, list):
                    # Multi-part content extraction
                    text_part = next((p["text"] for p in content if p["type"] == "text"), "")
                    content_str = text_part
                else:
                    content_str = str(content)
                existing_title = " ".join(content_str.split()[:4])
                if len(content_str.split()) > 4:
                    existing_title += "..."

        data = {
            "session_id": session_id,
            "title": existing_title,
            "created_at": existing_created_at,
            "messages": messages
        }
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to persist session %s: %s", session_id, e)

    def delete_session(self, session_id: str):
        """
        Deletes a persistent session from disk and memory.
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
        filepath = os.path.join(self.chats_dir, f"{session_id}.json")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                logger.info("Deleted persistent chat file: %s", filepath)
            except Exception as e:
                logger.error("Failed to delete persistent file %s: %s", filepath, e)

    async def converse(
        self, 
        session_id: str, 
        user_message: str, 
        vitals_context: Dict[str, Any] | None = None,
        media: Dict[str, Any] | None = None,
        search_enabled: bool = False,
        thinking_enabled: bool = False
    ) -> str:
        """
        Processes medical conversation with multimodal inputs, DDG search, web readers and CoT thinking.
        """
        # Load session from file if not in memory
        if session_id not in self.sessions:
            self.load_session(session_id)
            if session_id not in self.sessions:
                self.sessions[session_id] = []

        history = self.sessions[session_id]

        # 1. Check for URLs in user message and crawl them if found
        urls = re.findall(r'https?://[^\s]+', user_message)
        crawled_context = None
        if urls:
            crawled_context = ""
            for url in urls[:2]:
                crawled_text = await self.crawl_web_page(url)
                crawled_context += f"\n[OKUNAN WEB SAYFASI İÇERİĞİ: {url}]\n{crawled_text}\n"

        # 2. Fetch web search results if search is enabled
        search_results = None
        if search_enabled:
            search_results = await self.search_web(user_message)

        # 3. Build dynamic system prompt
        system_prompt = self._get_system_prompt(vitals_context, search_results, crawled_context, thinking_enabled)

        # 4. Construct current message content (handles multimodal input)
        if media:
            user_content = [
                {"type": "text", "text": user_message},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media['mime_type']};base64,{media['base64']}"
                    }
                }
            ]
        else:
            user_content = user_message

        # 5. Construct messages payload for OpenAI API
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
            
        messages.append({"role": "user", "content": user_content})

        if not self.client:
            # Fallback mock response
            thought = "<thought>Kullanıcı araması ve derin düşünmesi simüle ediliyor...</thought>\n" if thinking_enabled else ""
            mock_reply = (
                f"{thought}Merhaba! OpenAI API anahtarı girilmediği için demo modundayım.\n"
                f"Sorgunuz: '{user_message}'\n"
                f"Arama Durumu: {'Aktif' if search_enabled else 'Pasif'}\n"
                f"Görsel Durumu: {'Dosya Yüklendi' if media else 'Dosya Yüklenmedi'}"
            )
            # Save string version of user message to history
            history.append({"role": "user", "content": user_content})
            history.append({"role": "assistant", "content": mock_reply})
            self._save_session(session_id)
            return mock_reply

        try:
            completion = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=1200
            )
            reply = completion.choices[0].message.content or ""
            
            # Save history (we serialize user content with media payload to preserve image context)
            history.append({"role": "user", "content": user_content})
            history.append({"role": "assistant", "content": reply})
            
            if len(history) > self.max_history_len:
                self.sessions[session_id] = history[-self.max_history_len:]
            
            # Save to disk
            self._save_session(session_id)
            return reply
            
        except Exception as e:
            logger.error("Error in OpenAI Premium converse: %s", e)
            return (
                "Üzgünüm, şu anda yanıt üretemiyorum. Lütfen internet bağlantınızı veya API "
                "anahtarınızın limitlerini kontrol edip tekrar deneyin."
            )

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id] = []
        filepath = os.path.join(self.chats_dir, f"{session_id}.json")
        if os.path.exists(filepath):
            try:
                # Save empty history
                self._save_session(session_id, title="Sıfırlanmış Sohbet")
            except Exception:
                pass
        logger.info("Cleared in-memory and persisted history for session: %s", session_id)
