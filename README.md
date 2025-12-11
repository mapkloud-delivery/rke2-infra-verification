# RKE2 Altyapı Doğrulama

Bu proje, RKE2 Kubernetes kümesi için gerekli altyapı önkoşullarını doğrulayan bir Ansible rolüdür.

## Gereksinimler

Ansible playbook'u **Bastion host** üzerinde çalıştırılmalıdır. Bastion host'ta aşağıdakilerin yüklü olması gerekir:

- **Python 3** (Python 2 desteklenmez)
- **Ansible** (2.9 veya üzeri)
- **Geçerli SSH anahtarı** (Örnek : `~/.ssh/ssh_rke2_key`)

## Kurulum

### 1. Projeyi Klonlayın

Bastion host'a bağlanın ve projeyi klonlayın:

```bash
git clone https://github.com/mapkloud-delivery/rke2-infra-verification.git
cd rke2-infra-verification
```

### 2. Python Kontrolü ve Yükleme

Python 3'ün yüklü olduğunu kontrol edin:

```bash
python3 --version
```

Python 3 yüklü değilse, yükleyin:

```bash
# Ubuntu/Debian için
sudo apt update
sudo apt install -y python3 python3-pip
```

### 3. Inventory Dosyasını Oluşturun

`inventory.yml` dosyası hassas bilgiler (IP adresleri, SSH key path'leri) içerdiği için repo'da bulunmaz. Kendi inventory dosyanızı oluşturun:

```bash
cp inventory.yml.example inventory.yml
```

Ardından `inventory.yml` dosyasını düzenleyerek aşağıdaki placeholder'ları kendi değerlerinizle değiştirin:
- `<BASTION_IP>`, `<MASTER1_IP>`, `<MASTER2_IP>`, vb. → Gerçek IP adresleri
- `<BASTION_HOSTNAME>`, `<MASTER1_HOSTNAME>`, vb. → Gerçek hostname'ler
- `<SSH_USER>` → SSH kullanıcı adı (örn: `ubuntu`)
- `<SSH_KEY_NAME>` → SSH private key dosya adı (örn: `gcp_rke2_key`)
- `<WORKER1_MGMT_IP>`, `<WORKER1_DATA_IP>`, vb. → Worker node'ların management ve data IP'leri

**Not:** Network yapılandırması (VLAN network'leri, gateway'ler, LB VIP'leri) template dosyasında örnek olarak verilmiştir. Kendi network yapılandırmanıza göre güncelleyin.

Inventory dosyanızı oluşturduktan sonra, syntax ve yapı kontrolü için:

```bash
# Varsayılan olarak inventory.yml dosyasını kontrol eder
python3 scripts/check_inventory.py
# Farklı bir dosya belirtmek için
python3 scripts/check_inventory.py --inventory inventory.yml.example
```

Bu script şunları kontrol eder:
- YAML syntax geçerliliği
- Gerekli alanların varlığı
- Placeholder değerlerin değiştirilip değiştirilmediği
- IP adres formatlarının geçerliliği

### 4. SSH Anahtarını Yerleştirin

SSH anahtarınızı `~/.ssh/` konumuna yerleştirin ve gerekli izinleri verin:
Bu anahtar, **Bastion host**'tan tüm cluster nodelara SSH ile erişim sağlamak için kullanılacaktır. Nodelarda gerekli SSH yetkilendirmesinin önceden yapıldığı varsayılmaktadır.

```bash
chmod 600 ~/.ssh/<ssh-key>*
```

### 5. SSH Yapılandırmasını Doğrulayın

SSH yapılandırmasının doğru yapıldığını kontrol etmek için `ssh-kullanıcısı` ve `key-isimini` girdi olarak sağlayarak aşağıdaki scripti çalıştırabilirsiniz:

```bash
python3 scripts/check_ssh_config.py --user ubuntu --key ~/.ssh/ssh_rke2_key
```

Bu script şunları kontrol eder:
- Public key'in tüm hedef hostlarda `authorized_keys` dosyasında olup olmadığı
- Tüm host key'lerin bastion host'taki `known_hosts` dosyasında olup olmadığı

Script hiçbir değişiklik yapmaz, sadece doğrulama yapar.

### 6. Ansible Kontrolü ve Yükleme

Ansible'ın yüklü olduğunu kontrol edin:

```bash
ansible --version
```

Gerekirse Ansible'ı yükleyin:

```bash
# Ubuntu/Debian için
sudo apt update
pip3 install ansible

# Add ansible to $PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

## Kullanım

### Bağlantı Testi

Playbook'u çalıştırmadan önce, tüm hostlara bağlantıyı test edin:

```bash
ansible all -i inventory.yml -m ping
```

Tüm hostlar için `SUCCESS` mesajı almalısınız. Bağlantı sorunları varsa, önce bunları çözün.

### Tüm Kontrolleri Çalıştırma

Playbookları sırasıyla çalıştırın. Çıktı otomatik olarak tarihli bir dosyaya kaydedilir:

```bash
ansible-playbook -i inventory.yml prerequisites.yml --skip-tags network_advanced | tee "teknik_keşif_raporu_wona$(date +%Y%m%d).txt"

ansible-playbook -i inventory.yml prerequisites.yml --tags network_advanced | tee "teknik_keşif_raporu_na$(date +%Y%m%d).txt"
```

Bu komut hem ekranda gösterir hem de `teknik_keşif_raporu_YYYYMMDD.txt` formatında bir dosyaya kaydeder (örneğin: `teknik_keşif_raporu_wona20241215.txt`).

## Notlar
- Kontroller non-destructive (yıkıcı olmayan) işlemlerdir, sistemde değişiklik yapmazlar
