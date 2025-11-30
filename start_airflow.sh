#!/bin/bash
#
# Airflow MLOps Pipeline - Quick Start Script
# ===========================================
# Bu script Airflow environment'ını başlatır ve kontrol eder.

set -e  # Exit on error

echo "=========================================="
echo "AIRFLOW MLOPS PIPELINE - BAŞLATILIYOR"
echo "=========================================="

# Renkli output için
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Gerekli dizinleri oluştur
echo -e "\n${YELLOW}[1/5]${NC} Gerekli dizinler oluşturuluyor..."
mkdir -p logs plugins config data models
echo -e "${GREEN}✓${NC} Dizinler hazır"

# 2. Docker çalışıyor mu kontrol et
echo -e "\n${YELLOW}[2/5]${NC} Docker kontrol ediliyor..."
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} Docker çalışmıyor. Lütfen Docker Desktop'ı başlatın."
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker çalışıyor"

# 3. Airflow servislerini başlat
echo -e "\n${YELLOW}[3/5]${NC} Airflow servisleri başlatılıyor..."
echo "Bu işlem 2-3 dakika sürebilir (ilk seferde daha uzun)..."
docker-compose up -d

# 4. Servislerin hazır olmasını bekle
echo -e "\n${YELLOW}[4/5]${NC} Servisler hazır hale gelene kadar bekleniyor..."
echo "Postgres, Redis ve Airflow servisleri başlatılıyor..."

# Postgres'in hazır olmasını bekle
echo -n "Postgres: "
timeout=60
counter=0
while [ $counter -lt $timeout ]; do
    if docker-compose exec -T postgres pg_isready -U airflow > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 1
    counter=$((counter + 1))
done

if [ $counter -eq $timeout ]; then
    echo -e "${RED}✗${NC} Timeout"
    exit 1
fi

# Webserver'ın hazır olmasını bekle
echo -n "Airflow Webserver: "
timeout=120
counter=0
while [ $counter -lt $timeout ]; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
    counter=$((counter + 2))
done

if [ $counter -eq $timeout ]; then
    echo -e "${YELLOW}!${NC} Webserver henüz hazır değil, ama devam edebilirsiniz"
fi

# 5. Özet
echo -e "\n${YELLOW}[5/5]${NC} Kurulum tamamlandı!"
echo ""
echo "=========================================="
echo -e "${GREEN}✓ AIRFLOW BAŞARIYLA BAŞLATILDI${NC}"
echo "=========================================="
echo ""
echo "📊 Web UI: http://localhost:8080"
echo "   Username: airflow"
echo "   Password: airflow"
echo ""
echo "🚀 DAG'lar:"
echo "   • hospital_capacity_monthly_retrain"
echo "   • monthly_hospital_model_retrain"
echo ""
echo "💡 Yararlı komutlar:"
echo "   • docker-compose logs -f              # Logları izle"
echo "   • docker-compose down                 # Durdur"
echo "   • docker-compose restart              # Yeniden başlat"
echo "   • python retrain_real.py --status     # Model durumu"
echo ""
echo "📚 Detaylı bilgi: AIRFLOW_SETUP.md"
echo ""
echo "=========================================="

# DAG'ları listele (opsiyonel)
echo -e "\n${YELLOW}DAG Listesi:${NC}"
sleep 5  # Scheduler'ın DAG'ları parse etmesi için bekle
docker-compose exec -T airflow-scheduler airflow dags list 2>/dev/null | grep hospital || echo "DAG'lar henüz parse edilmedi, birkaç saniye bekleyin..."

echo ""
echo -e "${GREEN}Kurulum tamamlandı! Web UI'ya gidin: http://localhost:8080${NC}"
