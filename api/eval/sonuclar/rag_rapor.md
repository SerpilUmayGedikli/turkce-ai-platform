# Türkçe Belge Arama Raporu

50 soru, 47 parça (9 belge). Soru türleri: {'dogrudan': 16, 'cekim': 16, 'esanlam': 18}

## Genel

| Yöntem | Recall@1 | Recall@5 | MRR |
|---|---|---|---|
| bm25-ham | 50% | 74% | 0.59 |
| bm25-kok | 64% | 80% | 0.70 |
| bm25-on5 | 74% | 86% | 0.80 |
| vektor | 66% | 86% | 0.75 |
| hibrit-kok | 64% | 90% | 0.75 |
| hibrit-on5 | 72% | 94% | 0.80 |

## Soru türüne göre Recall@5

| Yöntem | dogrudan (16) | cekim (16) | esanlam (18) |
|---|---|---|---|
| bm25-ham | 100% | 69% | 56% |
| bm25-kok | 100% | 94% | 50% |
| bm25-on5 | 100% | 94% | 67% |
| vektor | 100% | 81% | 78% |
| hibrit-kok | 100% | 100% | 72% |
| hibrit-on5 | 100% | 100% | 83% |

## İlk 5'te bulunamayanlar

**bm25-ham** (13)

- Taksitlerle aldığım ürünü iade edersem param nasıl yatar? (sıra: 8)
- Puanlarımı nasıl harcarım? (sıra: yok)
- Arızalı ürünümü garantiye nasıl gönderirim? (sıra: yok)
- Garantisi bitmiş ürünlerin onarımı yapılıyor mu? (sıra: yok)
- Şikâyetlerime kaç günde dönüş yapılıyor? (sıra: yok)
- Pantolonun bedeni küçük geldi, büyüğüyle nasıl değiştiririm? (sıra: yok)
- Evde yokken kurye gelirse ne olur? (sıra: yok)
- Kutusu ezik gelen ürünü kabul etmeli miyim? (sıra: yok)
- Alışverişimi vazgeçip durdurmak istiyorum, henüz yola çıkmadı. (sıra: yok)
- Telefonum suya düştü, ücretsiz tamir edilir mi? (sıra: yok)
- Hangi bilgilerimi topluyorsunuz? (sıra: yok)
- Bilgilerim başka ülkelere gönderiliyor mu? (sıra: yok)
- Bir temsilciyle yazışarak konuşabilir miyim? (sıra: yok)

**bm25-kok** (10)

- İptal ettiğim siparişin ücreti kartıma ne zaman yatar? (sıra: 6)
- Pantolonun bedeni küçük geldi, büyüğüyle nasıl değiştiririm? (sıra: yok)
- Evde yokken kurye gelirse ne olur? (sıra: yok)
- Kutusu ezik gelen ürünü kabul etmeli miyim? (sıra: 15)
- Alışverişimi vazgeçip durdurmak istiyorum, henüz yola çıkmadı. (sıra: yok)
- Biri telefonda beni arayıp onay kodunu istedi, bu normal mi? (sıra: 10)
- Telefonum suya düştü, ücretsiz tamir edilir mi? (sıra: yok)
- Hangi bilgilerimi topluyorsunuz? (sıra: 8)
- Bilgilerim başka ülkelere gönderiliyor mu? (sıra: yok)
- Bir temsilciyle yazışarak konuşabilir miyim? (sıra: yok)

**bm25-on5** (7)

- İptal ettiğim siparişin ücreti kartıma ne zaman yatar? (sıra: 7)
- Evde yokken kurye gelirse ne olur? (sıra: yok)
- Kutusu ezik gelen ürünü kabul etmeli miyim? (sıra: 10)
- Alışverişimi vazgeçip durdurmak istiyorum, henüz yola çıkmadı. (sıra: yok)
- Telefonum suya düştü, ücretsiz tamir edilir mi? (sıra: yok)
- Hangi bilgilerimi topluyorsunuz? (sıra: 10)
- Bilgilerim başka ülkelere gönderiliyor mu? (sıra: 18)

**vektor** (7)

- Siparişlerimin kargo takibini nereden yaparım? (sıra: 7)
- Puanlarımı nasıl harcarım? (sıra: 28)
- Verilerimin silinmesini isteyebilir miyim? (sıra: 17)
- Alışverişimi vazgeçip durdurmak istiyorum, henüz yola çıkmadı. (sıra: 6)
- Bilgilerim başka ülkelere gönderiliyor mu? (sıra: 34)
- Kişisel bilgilerimle ilgili talebimi kime iletirim? (sıra: 6)
- Bir temsilciyle yazışarak konuşabilir miyim? (sıra: 17)

**hibrit-kok** (5)

- Kutusu ezik gelen ürünü kabul etmeli miyim? (sıra: 6)
- Alışverişimi vazgeçip durdurmak istiyorum, henüz yola çıkmadı. (sıra: 13)
- Telefonum suya düştü, ücretsiz tamir edilir mi? (sıra: 21)
- Bilgilerim başka ülkelere gönderiliyor mu? (sıra: 37)
- Bir temsilciyle yazışarak konuşabilir miyim? (sıra: 17)

**hibrit-on5** (3)

- Alışverişimi vazgeçip durdurmak istiyorum, henüz yola çıkmadı. (sıra: 13)
- Telefonum suya düştü, ücretsiz tamir edilir mi? (sıra: 23)
- Bilgilerim başka ülkelere gönderiliyor mu? (sıra: 24)

