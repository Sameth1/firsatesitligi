# hero/

`hero-object.glb` — açılış sahnesindeki 3D obje. Repoda yoksa `HeroCanvas`
prosedürel (shader tabanlı) objeyle çalışmaya devam eder; sahne bozulmaz.

Model Higgsfield ile üretildi (Recraft V4.1 görsel → Tripo H3.1 image-to-3D).
Yeniden üretmek ya da değiştirmek için: üretilen `.glb` dosyasını bu klasöre
`hero-object.glb` adıyla koymak yeterli.

Dosyayı repoya koymadan denemek için `.env.local` içine uzak URL verilebilir:

    NEXT_PUBLIC_HERO_MODEL_URL=https://.../model.glb

(Uzak URL kullanılıyorsa sunucunun CORS izni vermesi gerekir.)
