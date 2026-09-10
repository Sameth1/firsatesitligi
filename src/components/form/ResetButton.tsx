'use client'

/**
 * Bir form alanının seçimini kaldıran "Sıfırla" düğmesi.
 *
 * Eskiden her alanın köşesinde çerçevesiz, gri, küçük bir "temizle" metni
 * vardı — koyu zeminde düğme olduğu anlaşılmıyordu. Artık çerçeveli bir hap:
 * tıklanabilir görünen tıklanabilir. Üç kontrol (ChoiceGrid, RangeSlider,
 * StepSlider) aynı görünümü paylaşsın diye tek yerde duruyor.
 */

export default function ResetButton({ onClick, label = 'Sıfırla' }: {
  onClick: () => void
  /** Ekran okuyucuya hangi alanın sıfırlandığını söylemek için. */
  label?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="reset-btn"
      aria-label={label}
    >
      <span aria-hidden="true" style={{ fontSize: 12, lineHeight: 1 }}>↺</span>
      Sıfırla
    </button>
  )
}
