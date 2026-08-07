import jsQR from 'jsqr';

/**
 * Распознаёт QR-код на изображении (файл/Blob) прямо в браузере.
 *
 * Алгоритм:
 *  1. Загружаем картинку в <img> через URL.createObjectURL.
 *  2. Рисуем в <canvas>, получаем ImageData.
 *  3. jsQR сканирует пиксели и возвращает найденный текст QR.
 *
 * Возвращает строку (данные QR) или null, если QR не найден.
 */
export async function decodeQrFromImage(file: File | Blob): Promise<string | null> {
  const url = URL.createObjectURL(file);
  try {
    const img = await loadImage(url);
    const data = scanImage(img);
    return data;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Не удалось загрузить изображение'));
    img.src = src;
  });
}

function scanImage(img: HTMLImageElement): string | null {
  // Ограничиваем максимальный размер canvas, чтобы не тормозило на
  // больших скриншотах — QR и так хорошо читается при downscale.
  const MAX = 1200;
  let { naturalWidth: w, naturalHeight: h } = img;
  if (w === 0 || h === 0) return null;

  const scale = Math.min(1, MAX / Math.max(w, h));
  const cw = Math.max(1, Math.round(w * scale));
  const ch = Math.max(1, Math.round(h * scale));

  const canvas = document.createElement('canvas');
  canvas.width = cw;
  canvas.height = ch;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return null;
  ctx.drawImage(img, 0, 0, cw, ch);

  const imageData = ctx.getImageData(0, 0, cw, ch);
  const code = jsQR(imageData.data, imageData.width, imageData.height, {
    inversionAttempts: 'attemptBoth',
  });
  return code?.data ?? null;
}
