# photo-prep

Мікросервіс підготовки фото для n8n: HEIC/PNG/JPEG/WEBP → JPEG, поворот за EXIF,
ресайз, домінуючий колір.

## API

| Метод | Шлях | Що робить |
|---|---|---|
| GET  | `/health`  | `{"ok": true}` — використовується для healthcheck |
| POST | `/convert` | тіло = бінарні дані картинки → повертає JPEG/PNG. Заголовок відповіді `X-Dominant-Color` |
| POST | `/palette` | тіло = бінарні дані → `{"hex": "...", "palette": [...]}` |

Параметри `/convert`: `?fmt=jpeg|png` `&max_side=1600` `&q=85`

## Змінні оточення

| Змінна | За замовчуванням | Опис |
|---|---|---|
| `AUTH_TOKEN` | порожньо | Якщо задано — усі запити, крім `/health`, вимагають заголовок `X-Auth-Token` |

## Запуск локально

```bash
docker build -t photo-prep .
docker run -p 8080:8080 photo-prep
curl -F- --data-binary @photo.heic http://localhost:8080/convert -o out.jpg
```

## Налаштування ноди в n8n

Нода `Конвертація` у воркфлоу PHOTO_INGEST:

- Method: `POST`
- URL: `http://photo-prep:8080/convert?fmt=jpeg&max_side=1600&q=85`
- Body Content Type: `n8n Binary File`, Input Data Field Name: `data`
- Options → Response: Format `File`, Output Field `data`, увімкнути `Include Response Headers and Status`
- Якщо задано `AUTH_TOKEN` — додати заголовок `X-Auth-Token`
