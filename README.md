# RKE2 Altyapı Doğrulama

Bu proje, RKE2 Kubernetes kümesi için gerekli altyapı önkoşullarını doğrulayan bir Ansible rolüdür.

## Gereksinimler

Ansible playbook'u **Bastion host** üzerinde çalıştırılmalıdır. Bastion host'ta aşağıdakilerin yüklü olması gerekir:

- **Python 3** (Python 2 desteklenmez)
- **Ansible** (2.9 veya üzeri)
- **Geçerli SSH anahtarı** (`~/.ssh/ssh_rke2_key`)

## Kurulum

### 1. Projeyi Klonlayın

Bastion host'a bağlanın ve projeyi klonlayın:

```bash
git clone https://github.com/mapkloud-delivery/rke2-infra-verification.git
cd rke2-infra-verification
```

### 2. SSH Anahtarını Yerleştirin

SSH anahtarınızı `~/.ssh/ssh_rke2_key` konumuna yerleştirin ve gerekli izinleri verin:
Bu anahtar, **Bastion host**'tan tüm cluster nodelara SSH ile erişim sağlamak için kullanılacaktır. Nodelarda gerekli SSH yetkilendirmesinin önceden yapıldığı varsayılmaktadır.

```bash
chmod 600 ~/.ssh/ssh_rke2_key
```

### 3. Python ve Ansible Kontrolü

Python ve Ansible'ın yüklü olduğunu kontrol edin:

```bash
python3 --version
ansible --version
```

Gerekirse Ansible'ı yükleyin:

```bash
# Ubuntu/Debian için
sudo apt update
sudo apt install -y python3-pip
pip3 install ansible

# RHEL/CentOS için
sudo yum install -y python3-pip
pip3 install ansible

# Add ansible to $PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

## Kullanım

### Tüm Kontrolleri Çalıştırma

Playbook'u çalıştırın. Çıktı otomatik olarak tarihli bir dosyaya kaydedilir:

```bash
ansible-playbook -i inventory.yml prerequisites.yml | tee "teknik_keşif_raporu_$(date +%Y%m%d).txt"
```

Bu komut hem ekranda gösterir hem de `teknik_keşif_raporu_YYYYMMDD.txt` formatında bir dosyaya kaydeder (örneğin: `teknik_keşif_raporu_20241215.txt`).

## Çıktı

Playbook çalıştırıldığında, her host için yapılan kontrollerin sonuçları hem ekranda görüntülenir hem de `teknik_keşif_raporu_<tarih>.txt` dosyasına kaydedilir. Başarısız kontroller varsa, bunlar çıktıda belirtilecektir.

## Notlar
- Kontroller non-destructive (yıkıcı olmayan) işlemlerdir, sistemde değişiklik yapmazlar
