"""Türkçe belge arama test seti: soru -> cevabın bulunduğu parça (altın).

Etiketler (her soruda bir tane):
  dogrudan : soru, belgedeki kelimeleri büyük ölçüde AYNI biçimde kullanır
  cekim    : aynı kökler, FARKLI ekler ("iade" -> "iadelerde", "kargo" -> "kargodaki")
  esanlam  : aynı anlam, FARKLI kelimeler ("para iadesi" -> "paramı ne zaman geri alırım")

Hipotez: kök bulma "cekim" sorularında, embedding "esanlam" sorularında fark yaratır;
hibrit arama ikisinde de iyidir.

Dürüstlük notu: sorular ve belgeler aynı kişi tarafından yazıldı; gerçek kullanıcı sorularından
daha "temiz" olabilirler. Sorular, yöntemlerin sonuçları görülmeden önce yazıldı ve sonuçlara
bakılarak değiştirilmedi.
"""

IADE, KARGO, IPTAL, ODEME = "iade-ve-degisim", "kargo-ve-teslimat", "siparis-iptali", "odeme-ve-fatura"
GARANTI, KVKK, UYELIK = "garanti-ve-teknik-servis", "kvkk-aydinlatma-metni", "uyelik-ve-hesap"
KAMPANYA, DESTEK = "kampanya-ve-puan", "musteri-hizmetleri"


def _s(soru: str, belge: str, baslik: str, etiket: str, *diger: str) -> dict:
    """diger: cevabın gerçekten bulunduğu başka parçalar ("belge::başlık"); biri bulunursa doğru."""
    return {"soru": soru, "altin": [f"{belge}::{baslik}", *diger], "etiket": etiket}


SORULAR = [
    # ------------------------------------------------------------- dogrudan
    _s("İade süresi kaç gün?", IADE, "İade süresi", "dogrudan"),
    _s("Ücretsiz kargo için sipariş tutarı ne kadar olmalı?", KARGO, "Ücretsiz kargo", "dogrudan"),
    _s("Kapıda ödeme hizmet bedeli ne kadar?", ODEME, "Kapıda ödeme", "dogrudan"),
    _s("Taksit seçenekleri nelerdir?", ODEME, "Taksit seçenekleri", "dogrudan"),
    _s("Elektronik ürünlerin garanti süresi ne kadar?", GARANTI, "Garanti süresi", "dogrudan"),
    _s("Kişisel verilerin saklama süresi nedir?", KVKK, "Saklama süresi", "dogrudan"),
    _s("Müşteri hizmetleri çalışma saatleri nedir?", DESTEK, "Çalışma saatleri", "dogrudan"),
    _s("İlk sipariş indirimi ne kadar?", KAMPANYA, "İlk sipariş indirimi", "dogrudan"),
    _s("Kurumsal fatura nasıl alınır?", ODEME, "Fatura", "dogrudan"),
    _s("Hasarlı paket gelirse ne yapmalıyım?", KARGO, "Hasarlı paket", "dogrudan"),
    _s("Servis süresi en fazla kaç iş günü?", GARANTI, "Servis süresi", "dogrudan"),
    _s("Bir siparişte birden fazla kupon kullanılabilir mi?", KAMPANYA, "Kupon kullanımı", "dogrudan"),
    _s("Kısmi iptal nasıl yapılır?", IPTAL, "Kısmi iptal", "dogrudan"),
    _s("Tüketici hakem heyetine nasıl başvurulur?", DESTEK, "Tüketici hakem heyeti", "dogrudan"),
    _s("Hesabımı nasıl kapatabilirim?", UYELIK, "Hesabı kapatma", "dogrudan"),
    _s("Pil ve batarya garanti kapsamında mı?", GARANTI, "Garanti kapsamı dışındaki durumlar", "dogrudan"),
    # ------------------------------------------------------------- cekim
    _s("İadelerde kargo ücretini kim ödüyor?", IADE, "İade kargo ücreti", "cekim"),
    _s("Kargodaki siparişimi iptal edebilir miyim?", IPTAL, "Kargodaki siparişin iptali", "cekim"),
    _s("Kozmetiklerin iadesi kabul ediliyor mu?", IADE, "İade edilemeyen ürünler", "cekim"),
    _s("Taksitlerle aldığım ürünü iade edersem param nasıl yatar?", IADE, "Para iadesi ne zaman yapılır", "cekim"),
    _s("Siparişlerimin kargo takibini nereden yaparım?", KARGO, "Kargo takibi", "cekim"),
    _s("Puanlarımı nasıl harcarım?", KAMPANYA, "Sadakat puanı harcama", "cekim"),
    _s("Kuponlu siparişlerimi iade edince kuponum geri yüklenir mi?", KAMPANYA, "Kuponlu siparişin iadesi", "cekim"),
    _s("Arızalı ürünümü garantiye nasıl gönderirim?", GARANTI, "Arıza bildirimi", "cekim"),
    _s("Şifremi unutursam hesabıma nasıl girerim?", UYELIK, "Şifremi unuttum", "cekim"),
    _s("Verilerimin silinmesini isteyebilir miyim?", KVKK, "Haklarınız", "cekim"),
    _s("Siparişimin adresini değiştirebilir miyim?", KARGO, "Adres değişikliği", "cekim"),
    _s("Hazırlanan siparişimi iptal edersem ücret kesilir mi?", IPTAL, "Kargoya verilmemiş siparişin iptali", "cekim"),
    _s("İptal ettiğim siparişin ücreti kartıma ne zaman yatar?", IPTAL, "İptal edilen siparişin ödemesi", "cekim"),
    _s("Kampanya e-postalarından nasıl çıkarım?", UYELIK, "Bildirim ve ileti izinleri", "cekim"),
    _s("Garantisi bitmiş ürünlerin onarımı yapılıyor mu?", GARANTI, "Garanti sonrası onarım", "cekim"),
    _s("Şikâyetlerime kaç günde dönüş yapılıyor?", DESTEK, "Şikâyet ve öneriler", "cekim"),
    # ------------------------------------------------------------- esanlam
    _s("Paramı ne zaman geri alırım?", IADE, "Para iadesi ne zaman yapılır", "esanlam",
       f"{IPTAL}::İptal edilen siparişin ödemesi"),
    _s("Aldığım şeyi beğenmezsem kaç gün içinde geri yollayabilirim?", IADE, "İade süresi", "esanlam"),
    _s("Pantolonun bedeni küçük geldi, büyüğüyle nasıl değiştiririm?", IADE, "Değişim", "esanlam"),
    _s("Paketim ne zaman elime ulaşır?", KARGO, "Teslimat süresi", "esanlam"),
    _s("Evde yokken kurye gelirse ne olur?", KARGO, "Teslim edilemeyen paketler", "esanlam"),
    _s("Kutusu ezik gelen ürünü kabul etmeli miyim?", KARGO, "Hasarlı paket", "esanlam"),
    _s("Alışverişimi vazgeçip durdurmak istiyorum, henüz yola çıkmadı.", IPTAL,
       "Kargoya verilmemiş siparişin iptali", "esanlam"),
    _s("Mağaza benim alışverişimi neden iptal etmiş olabilir?", IPTAL, "Mağazanın siparişi iptal etmesi", "esanlam"),
    _s("Kart bilgilerim sitede tutuluyor mu, güvende mi?", ODEME, "Ödeme yöntemleri", "esanlam",
       f"{KVKK}::İşlenen kişisel veriler"),
    _s("Biri telefonda beni arayıp onay kodunu istedi, bu normal mi?", ODEME, "Ödeme güvenliği", "esanlam"),
    _s("Telefonum suya düştü, ücretsiz tamir edilir mi?", GARANTI, "Garanti kapsamı dışındaki durumlar", "esanlam"),
    _s("Hangi bilgilerimi topluyorsunuz?", KVKK, "İşlenen kişisel veriler", "esanlam"),
    _s("Bilgilerim başka ülkelere gönderiliyor mu?", KVKK, "Verilerin işlenme amaçları", "esanlam"),
    _s("Kişisel bilgilerimle ilgili talebimi kime iletirim?", KVKK, "Başvuru yolu", "esanlam"),
    _s("Kayıt olmadan alışveriş yapabilir miyim?", UYELIK, "Üye olmak", "esanlam"),
    _s("Alışveriş yaptıkça biriken ödüller nasıl kazanılıyor?", KAMPANYA, "Sadakat puanı kazanma", "esanlam"),
    _s("Bir temsilciyle yazışarak konuşabilir miyim?", DESTEK, "Canlı destek ve WhatsApp", "esanlam"),
    _s("Şirketimiz için çok sayıda ürün almak istiyoruz.", DESTEK, "Kurumsal satış", "esanlam"),
]
