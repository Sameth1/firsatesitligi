# hero/

`hero-object.glb` — açılış sahnesindeki 3D obje (mezuniyet kepi). Repoda yoksa
`HeroCanvas` prosedürel (shader tabanlı) objeyle çalışmaya devam eder; sahne
bozulmaz.

Model Higgsfield ile üretildi: `nano_banana_pro` ile siyah zeminde cam/iridesan
bir kep görseli → `image_to_3d` ile GLB. Model dokusuz (`should_texture: false`)
üretiliyor; `HeroCanvas` mesh'e kendi iridesan cam shader'ını uyguluyor, bu
yüzden sahnede ışık kurmaya gerek yok ve obje sitenin geri kalanıyla aynı
görsel dili konuşuyor.

Yeniden üretmek ya da değiştirmek için: üretilen `.glb` dosyasını bu klasöre
`hero-object.glb` adıyla koymak yeterli.

Dosyayı repoya koymadan denemek için `.env.local` içine uzak URL verilebilir:

    NEXT_PUBLIC_HERO_MODEL_URL=https://.../model.glb

(Uzak URL kullanılıyorsa sunucunun CORS izni vermesi gerekir.)
