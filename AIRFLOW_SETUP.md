# Airflow MLOps Pipeline - Kurulum ve Çalıştırma

Bu döküman, Hospital Capacity Prediction projesinin Airflow MLOps pipeline'ını nasıl başlatacağınızı ve kullanacağınızı açıklar.

## Hızlı Başlangıç

### 1. Gerekli Dizinleri Oluşturun

```bash
mkdir -p logs plugins config
```

### 2. Airflow'u Başlatın

```bash
# Tüm servisleri başlat
docker-compose up -d

# Logları izle (opsiyonel)
docker-compose logs -f
```

İlk başlatma 2-3 dakika sürebilir çünkü:
- PostgreSQL ve Redis başlatılacak
- Airflow database migration yapılacak
- Admin kullanıcısı oluşturulacak
- Python paketleri yüklenecek (scikit-learn, pandas, pytrends, vb.)

### 3. Web UI'ya Erişin

Tarayıcıda açın: http://localhost:8080

**Giriş bilgileri:**
- Username: `airflow`
- Password: `airflow`

### 4. DAG'ları Aktifleştirin

Web UI'da:
1. "DAGs" sekmesine gidin
2. İki DAG göreceksiniz:
   - `hospital_capacity_monthly_retrain` - Gerçek NHS verisiyle aylık yeniden eğitim
   - `monthly_hospital_model_retrain` - Zenginleştirilmiş özelliklerle eğitim
3. Her birinin solundaki toggle'ı aktif edin

## Mevcut DAG'lar

### 1. hospital_capacity_monthly_retrain

**Zamanlama:** Ayda bir (Her ayın 1'inde saat 02:00)

**İş akışı:**
```
start → fetch_hospital_data ┐
        fetch_weather_data   ├→ prepare_data → train_model → evaluate_and_decide
        fetch_trends_data   ┘                                      ↓
                                                              promote / skip
                                                                    ↓
                                                            send_notification → end
```

**Ne yapar:**
- NHS hospital data, hava durumu ve Google Trends verilerini çeker
- Verileri birleştirir ve zenginleştirir
- Aday model eğitir (XGBoost)
- Mevcut üretim modeliyle karşılaştırır
- AUC ≥ 0.70 ve min %1 iyileşme varsa terfi ettirir

### 2. monthly_hospital_model_retrain

**Zamanlama:** Ayda bir (@monthly)

**İş akışı:**
```
start → fetch_external_data → prepare_training_data → train_candidate
                                                            ↓
                                                   evaluate_and_branch
                                                      ↙         ↘
                                            promote_model    skip_promotion
                                                      ↘         ↙
                                                         end
```

**Ne yapar:**
- NHS 111 call data çeker
- Takvim, hava kalitesi ve NHS 111 özellikleriyle zenginleştirir
- Aday model eğitir
- AUC ≥ 0.94 ve min %0.5 iyileşme varsa terfi ettirir

## Manuel Çalıştırma

### Web UI'dan

1. DAG'a tıklayın
2. Sağ üstte "Trigger DAG" butonuna basın
3. "Graph" görünümünden task'ların durumunu izleyin

### CLI'dan

```bash
# Container'a girin
docker-compose exec airflow-scheduler bash

# DAG'ı manuel tetikle
airflow dags trigger hospital_capacity_monthly_retrain

# DAG durumunu kontrol et
airflow dags list

# Task loglarını görüntüle
airflow tasks logs hospital_capacity_monthly_retrain train_model <execution_date>
```

## Servis Yönetimi

```bash
# Tüm servisleri durdur
docker-compose down

# Servisleri yeniden başlat
docker-compose restart

# Sadece belirli bir servisi yeniden başlat
docker-compose restart airflow-scheduler

# Container'ları ve volume'ları tamamen sil (dikkat!)
docker-compose down -v
```

## Standalone Test (Airflow olmadan)

DAG'ları Airflow olmadan test edebilirsiniz:

```bash
# İlk DAG'ı test et
python dags/hospital_capacity_dag.py

# İkinci DAG'ı test et
python dags/monthly_hospital_model_retrain.py

# retrain_real.py script'i de kullanılabilir
python retrain_real.py                    # Tam pipeline
python retrain_real.py --status           # Durum kontrolü
python retrain_real.py --prepare-only     # Sadece veri hazırlama
python retrain_real.py --train-only       # Sadece eğitim
```

## Troubleshooting

### DAG'lar görünmüyor

```bash
# DAG'ları tara
docker-compose exec airflow-scheduler airflow dags list

# DAG parse hatalarını kontrol et
docker-compose exec airflow-scheduler airflow dags list-import-errors
```

### Import hataları

```bash
# Container içinde Python path'i kontrol et
docker-compose exec airflow-scheduler python -c "import sys; print('\n'.join(sys.path))"

# src modülünün erişilebilir olduğunu doğrula
docker-compose exec airflow-scheduler ls -la /opt/airflow/src
```

### Task'lar başarısız oluyor

```bash
# Task log dosyalarını görüntüle
docker-compose logs airflow-scheduler | grep ERROR

# Specific task logunu görüntüle
docker-compose exec airflow-scheduler cat /opt/airflow/logs/hospital_capacity_monthly_retrain/train_model/<date>/<try>.log
```

### Veri dosyaları bulunamıyor

```bash
# Volume mapping'leri kontrol et
docker-compose exec airflow-scheduler ls -la /opt/airflow/
docker-compose exec airflow-scheduler ls -la /opt/airflow/data/
docker-compose exec airflow-scheduler ls -la /opt/airflow/models/

# Eğer dosyalar yoksa, host'tan kopyala
docker cp Fact_GA_Beds.csv <container_id>:/opt/airflow/
```

## Monitoring

### Metrics Log

Model performansını takip edin:

```bash
cat models/metrics_log.csv
```

Sütunlar:
- `timestamp`: Değerlendirme zamanı
- `candidate_auc`: Aday model AUC'si
- `production_auc`: Üretim model AUC'si
- `promoted`: Terfi edildi mi? (True/False)
- `improvement`: İyileşme miktarı

### Airflow Flower (Celery Monitoring)

```bash
# Flower'ı başlat
docker-compose --profile flower up -d

# Erişim
# http://localhost:5555
```

## Dosya Yapısı

```
.
├── dags/
│   ├── hospital_capacity_dag.py           # Ana DAG (gerçek veri)
│   └── monthly_hospital_model_retrain.py  # Zenginleştirilmiş DAG
├── src/
│   ├── data_preparation.py                # Veri hazırlama
│   ├── training.py                        # Model eğitimi
│   ├── evaluation.py                      # Model değerlendirme
│   └── enrich_features.py                 # Özellik zenginleştirme
├── data/
│   ├── training_data_real.csv             # Hazırlanmış eğitim verisi
│   └── hospital_capacity_enriched.csv     # Zenginleştirilmiş veri
├── models/
│   ├── candidate_model.pkl                # Aday model
│   ├── production_model.pkl               # Üretim modeli
│   └── metrics_log.csv                    # Metrik geçmişi
├── logs/                                  # Airflow log'ları
├── docker-compose.yaml                    # Airflow servisleri
└── retrain_real.py                        # Standalone script
```

## Production Notları

**Güvenlik:**
- Default şifreleri değiştirin
- `AIRFLOW__CORE__FERNET_KEY` ayarlayın
- Email notification için SMTP konfigürasyonu yapın

**Ölçeklendirme:**
- Worker sayısını artırın: `docker-compose up -d --scale airflow-worker=3`
- Postgres ve Redis için production-grade configuration kullanın

**Monitoring:**
- Prometheus/Grafana entegrasyonu ekleyin
- Log aggregation (ELK Stack) kurun
- Alert'ler için PagerDuty/Slack webhook'ları ayarlayın
