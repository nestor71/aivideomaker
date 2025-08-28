# 🚀 GUIDA COMPLETA DEPLOY AIVIDEOMAKER SU DIGITALOCEAN

**Guida step-by-step per mettere online il tuo sistema AIVideoMaker Freemium**

---

## 📋 INDICE

1. [Prerequisiti](#-prerequisiti)
2. [Preparazione Repository](#-preparazione-repository)
3. [Setup Account DigitalOcean](#-setup-account-digitalocean)
4. [Configurazione Database](#-configurazione-database)
5. [Deploy dell'Applicazione](#-deploy-dellapplicazione)
6. [Configurazione Dominio](#-configurazione-dominio)
7. [Setup Servizi Esterni](#-setup-servizi-esterni)
8. [Test e Verifica](#-test-e-verifica)
9. [Monitoraggio](#-monitoraggio)
10. [Troubleshooting](#-troubleshooting)

---

## 🎯 PREREQUISITI

### Account Necessari
- [ ] **DigitalOcean Account** (cloud.digitalocean.com)
- [ ] **GitHub Account** (per repository)
- [ ] **Stripe Account** (per pagamenti)
- [ ] **Google Developer Console** (per OAuth)
- [ ] **Dominio** (opzionale ma raccomandato)

### Costi Stimati
```
💰 COSTI MENSILI DIGITALOCEAN:
├── App Platform (1GB): $12/mese
├── PostgreSQL Database: $15/mese  
├── Redis: $15/mese
├── Bandwidth: Incluso
└── TOTALE: ~$42/mese

🎯 PRIMO MESE GRATIS con crediti DigitalOcean!
```

---

## 📁 PREPARAZIONE REPOSITORY

### Step 1: Crea Repository GitHub

```bash
# 1. Vai su github.com
# 2. New Repository
# 3. Nome: aivideomaker-freemium
# 4. Public/Private (a tua scelta)
# 5. Create repository
```

### Step 2: Carica il Progetto

```bash
# Nel tuo computer, nella cartella AIVideoMaker:
cd "/Users/nestor/Desktop/Progetti Claude-Code/AIVideoMaker"

# Inizializza Git (se non già fatto)
git init

# Aggiungi tutti i file
git add .

# Primo commit
git commit -m "🎉 AIVideoMaker Freemium - Sistema completo enterprise"

# Collega al repository GitHub (sostituisci con il tuo URL)
git remote add origin https://github.com/TUO_USERNAME/aivideomaker-freemium.git

# Carica tutto su GitHub
git push -u origin main
```

### Step 3: Verifica File Deployment

Assicurati che questi file siano nel repository:
```
✅ docker-compose.yml
✅ Dockerfile  
✅ .env.example
✅ requirements.txt
✅ README.md
✅ main.py
✅ app/ (cartella completa)
```

---

## 🌊 SETUP ACCOUNT DIGITALOCEAN

### Step 1: Registrazione

1. **Vai su** [cloud.digitalocean.com](https://cloud.digitalocean.com)
2. **Sign Up** con email
3. **Verifica email** e accedi
4. **Aggiungi carta di credito** (per attivazione)

### Step 2: Ottieni Crediti Gratuiti

```
🎁 CREDITI GRATUITI DISPONIBILI:
├── Studenti: $200 con GitHub Student Pack
├── Nuovi utenti: $100-200 con promo codes
├── Referral: $25 con link amici
└── Promo codes online: Cerca "DigitalOcean promo 2024"
```

### Step 3: Navigazione Dashboard

```
📊 DASHBOARD DIGITALOCEAN:
├── Create → Per creare risorse
├── Projects → Organizzare applicazioni  
├── Billing → Controllo costi
└── Account → Impostazioni
```

---

## 🗄️ CONFIGURAZIONE DATABASE

### Step 1: Crea Database PostgreSQL

1. **Dashboard DigitalOcean** → **Create** → **Databases**
2. **Scegli PostgreSQL** versione 15
3. **Configurazione:**
   ```
   Database Engine: PostgreSQL 15
   Datacenter: Frankfurt (per EU) o New York (per US)
   Plan: Basic ($15/mese - 1GB RAM, 10GB storage)
   Database name: aivideomaker
   ```
4. **Create Database**

### Step 2: Crea Database Redis

1. **Create** → **Databases** → **Redis**
2. **Configurazione:**
   ```
   Database Engine: Redis 7
   Datacenter: Stesso del PostgreSQL
   Plan: Basic ($15/mese - 25MB)
   ```
3. **Create Database**

### Step 3: Ottieni Connection Strings

Dopo la creazione (5-10 minuti):

```bash
# PostgreSQL - Copia da DigitalOcean dashboard
DATABASE_URL=postgresql://username:password@host:port/database?sslmode=require

# Redis - Copia da DigitalOcean dashboard  
REDIS_URL=rediss://username:password@host:port/0?ssl_cert_reqs=required
```

**💾 SALVA QUESTI VALORI** - Li userai nel prossimo step!

---

## 🚀 DEPLOY DELL'APPLICAZIONE

### Step 1: Crea App Platform

1. **Dashboard DigitalOcean** → **Create** → **Apps**
2. **Connect Source Code:**
   ```
   Source: GitHub
   Repository: TUO_USERNAME/aivideomaker-freemium
   Branch: main
   Autodeploy: ✅ Abilitato
   ```
3. **Next**

### Step 2: Configura App Settings

**DigitalOcean auto-rileva il Dockerfile!**

```yaml
# Configurazione automatica rilevata:
Name: aivideomaker-app
Type: Web Service  
Source Directory: /
Dockerfile: ./Dockerfile
Port: 8000
Instance Count: 1
Instance Size: Basic (1GB RAM) - $12/mese
```

### Step 3: Aggiungi Variabili Ambiente

Nella sezione **Environment Variables**, aggiungi:

```bash
# APPLICAZIONE
APP_NAME=AIVideoMaker
ENVIRONMENT=production
DEBUG=false

# URL (lascia vuoto per ora, lo configuriamo dopo)
FRONTEND_URL=https://TUA-APP-URL.ondigitalocean.app
BACKEND_URL=https://TUA-APP-URL.ondigitalocean.app

# DATABASE (incolla i valori salvati prima)
DATABASE_URL=postgresql://username:password@host:port/database?sslmode=require
REDIS_URL=rediss://username:password@host:port/0?ssl_cert_reqs=required

# JWT (genera una chiave forte)
JWT_SECRET=your-super-secret-32-characters-minimum-key-here-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

# STRIPE (configurerai dopo)
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PREMIUM_PRICE_ID=price_...

# OAUTH (configurerai dopo)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# EMAIL (configurerai dopo)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@aivideomaker.com

# GDPR
PRIVACY_POLICY_VERSION=2.0
DATA_DELETION_GRACE_PERIOD_DAYS=30

# RATE LIMITING  
FREE_TIER_VIDEO_MINUTES_MONTHLY=10
FREE_TIER_MAX_VIDEO_DURATION_MINUTES=1
PREMIUM_TIER_VIDEO_MINUTES_MONTHLY=-1
```

### Step 4: Review e Deploy

1. **Review** tutte le impostazioni
2. **Total cost: ~$42/mese** (App + Database + Redis)
3. **Create Resources** 🚀

**⏱️ Deploy in corso: 5-15 minuti**

### Step 5: Ottieni URL App

Dopo il deploy:
```
🌐 La tua app sarà disponibile a:
https://aivideomaker-app-xxxxx.ondigitalocean.app
```

**📝 AGGIORNA** le variabili `FRONTEND_URL` e `BACKEND_URL` con questo URL!

---

## 🌐 CONFIGURAZIONE DOMINIO

### Step 1: Dominio Custom (Opzionale)

Se hai un dominio (es: aivideomaker.com):

1. **App Settings** → **Domains**
2. **Add Domain**: `aivideomaker.com`
3. **Add Domain**: `www.aivideomaker.com` 
4. **DigitalOcean** ti darà dei **CNAME records**

### Step 2: Configura DNS

Nel tuo provider dominio (GoDaddy, Namecheap, etc):

```
Tipo: CNAME
Nome: @
Valore: aivideomaker-app-xxxxx.ondigitalocean.app

Tipo: CNAME  
Nome: www
Valore: aivideomaker-app-xxxxx.ondigitalocean.app
```

### Step 3: SSL Automatico

DigitalOcean configura **SSL gratuito automaticamente**!

```
✅ HTTP → HTTPS redirect automatico
✅ Certificato Let's Encrypt  
✅ Rinnovo automatico
```

---

## 🔧 SETUP SERVIZI ESTERNI

### 🟡 Stripe Setup

#### Step 1: Crea Account Stripe
1. **Vai su** [stripe.com](https://stripe.com)
2. **Sign up** business account
3. **Attiva account** con documenti business

#### Step 2: Crea Prodotto Premium
```
Dashboard Stripe → Products → Add Product:
Name: AIVideoMaker Premium  
Price: $9.99 USD
Billing: Recurring monthly
```

#### Step 3: Ottieni API Keys
```
Dashboard → Developers → API Keys:
Publishable key: pk_test_... (per frontend)
Secret key: sk_test_... (per backend)
```

#### Step 4: Configura Webhook
```
Dashboard → Developers → Webhooks → Add endpoint:
URL: https://tua-app-url.com/api/webhooks/stripe
Events: 
  - invoice.payment_succeeded
  - invoice.payment_failed
  - customer.subscription.deleted
  - customer.subscription.updated
```

#### Step 5: Aggiorna Variabili DigitalOcean
```
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_... (dal webhook creato)
STRIPE_PREMIUM_PRICE_ID=price_... (dal prodotto creato)
```

### 🟢 Google OAuth Setup

#### Step 1: Console Developer
1. **Vai su** [console.developers.google.com](https://console.developers.google.com)
2. **Crea progetto** "AIVideoMaker"
3. **Abilita Google+ API**

#### Step 2: Crea Credenziali OAuth
```
Credentials → Create Credentials → OAuth 2.0 Client ID:
Application type: Web application
Name: AIVideoMaker OAuth
Authorized redirect URIs: 
  - https://tua-app-url.com/api/auth/google/callback
```

#### Step 3: Aggiorna Variabili
```
GOOGLE_CLIENT_ID=123456...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-abcdef...
```

### 📧 Email SMTP Setup

#### Opzione A: Gmail (Gratuito)
```
1. Gmail → Impostazioni → Sicurezza
2. Attiva "App meno sicure" o crea "Password App"
3. Usa le credenziali:
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587  
   SMTP_USERNAME=tua-email@gmail.com
   SMTP_PASSWORD=password-app-generata
```

#### Opzione B: SendGrid (Professionale)
```
1. Registrati su sendgrid.com
2. Crea API Key
3. Configura:
   SMTP_HOST=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USERNAME=apikey
   SMTP_PASSWORD=SG.xxx (la tua API key)
```

---

## ✅ TEST E VERIFICA

### Step 1: Health Check

Visita: `https://tua-app-url.com/health`

**Risposta attesa:**
```json
{
  "status": "healthy",
  "timestamp": "2024-08-27T...",
  "version": "1.0.0",
  "database": "connected",
  "redis": "connected"
}
```

### Step 2: Test Registrazione

1. **Vai su** `https://tua-app-url.com`
2. **Click "Registrati"**
3. **Compila form** registrazione
4. **Verifica email** funziona
5. **Login** con credenziali

### Step 3: Test Upload Video

1. **Login** al sistema
2. **Upload** un video piccolo (test)
3. **Verifica processing** funziona
4. **Check watermark** su video gratuiti

### Step 4: Test Pagamento

1. **Click "Upgrade Premium"**
2. **Usa carta test Stripe:**
   ```
   Numero: 4242 4242 4242 4242
   Scadenza: 12/25
   CVC: 123
   ```
3. **Verifica upgrade** a premium
4. **Test video senza watermark**

### Step 5: Test GDPR

1. **Vai su** `/privacy`
2. **Test consensi** on/off
3. **Request data export**
4. **Verifica email** ricevuta

---

## 📊 MONITORAGGIO

### Dashboard DigitalOcean

```
App → Insights:
├── 📈 CPU & Memory usage  
├── 📊 Request metrics
├── 🚨 Error rates
├── 📋 Logs real-time
└── 💾 Database performance
```

### Alerts Setup

```
App Settings → Alerts:
├── CPU > 80% 
├── Memory > 90%
├── Error rate > 5%
├── Response time > 2s
└── Database connections > 80%
```

### Custom Monitoring

Aggiungi al tuo codice:
```python
# app/monitoring.py
import psutil
import time

def get_system_stats():
    return {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "timestamp": time.time()
    }
```

---

## 🚨 TROUBLESHOOTING

### Problema: App non si avvia

**Sintomi:** Build fallisce o app crash

**Soluzione:**
```bash
# 1. Check logs DigitalOcean
App → Runtime Logs

# 2. Verifica variabili ambiente
Controlla DATABASE_URL format

# 3. Test locale
docker-compose up --build

# 4. Check dipendenze
Verifica requirements.txt aggiornato
```

### Problema: Database connection failed

**Sintomi:** Errori di connessione DB

**Soluzione:**
```bash
# 1. Verifica DATABASE_URL
Deve iniziare con postgresql:// 
Deve avere ?sslmode=require alla fine

# 2. Check database status
DigitalOcean → Databases → Status

# 3. Test connessione
psql "postgresql://user:pass@host:port/db?sslmode=require"
```

### Problema: Pagamenti non funzionano

**Sintomi:** Errori Stripe webhook

**Soluzione:**
```bash
# 1. Verifica webhook URL
Deve essere: https://tua-app/api/webhooks/stripe

# 2. Check eventi attivati
invoice.payment_succeeded
customer.subscription.deleted

# 3. Test webhook
Stripe Dashboard → Webhooks → Send test webhook
```

### Problema: Email non inviate

**Sintomi:** Email non arrivano

**Soluzione:**
```bash
# 1. Verifica SMTP settings
Test con telnet smtp.gmail.com 587

# 2. Check password app Gmail
Genera nuova password app

# 3. Verifica from_email
Deve essere dominio verificato
```

### Problema: Video processing lento

**Sintomi:** Timeout elaborazione

**Soluzione:**
```bash
# 1. Aumenta instance size
App Settings → Basic → Professional (2GB RAM)

# 2. Ottimizza video processing
Riduci qualità per preview

# 3. Add timeout
Aumenta timeout Nginx se necessario
```

---

## 💡 OTTIMIZZAZIONI

### Performance

```yaml
# Scala app per traffic alto
App Settings → Scaling:
Instance Count: 3
Load Balancer: Automatic
```

### Database

```bash
# Upgrade database per performance
Database Settings → Resize:
Plan: Professional (4GB RAM)
```

### CDN

```bash
# Aggiungi CDN per file statici
Create → Spaces CDN
Collega a app per static files
```

### Backup

```bash
# Backup automatici database
Database Settings → Backups:
Daily backups: ✅ Enabled
Retention: 7 days
```

---

## 🎯 CHECKLIST GO-LIVE

### Pre-Launch
- [ ] ✅ App deployata e funzionante
- [ ] ✅ Database PostgreSQL + Redis connessi
- [ ] ✅ SSL certificato attivo
- [ ] ✅ Dominio personalizzato configurato (opzionale)
- [ ] ✅ Stripe prodotto e webhook configurati
- [ ] ✅ Google OAuth funzionante
- [ ] ✅ Email SMTP configurato
- [ ] ✅ Test registrazione + login completi
- [ ] ✅ Test upload + processing video
- [ ] ✅ Test pagamento premium
- [ ] ✅ Test GDPR compliance

### Post-Launch
- [ ] ✅ Monitoring e alerts attivati
- [ ] ✅ Backup database automatici
- [ ] ✅ Performance optimization
- [ ] ✅ SEO e analytics configurati
- [ ] ✅ Social media setup
- [ ] ✅ Customer support email
- [ ] ✅ Privacy policy e terms of service
- [ ] ✅ Marketing landing page

---

## 🎉 CONGRATULAZIONI!

**🎬 Il tuo AIVideoMaker Freemium è ora LIVE e ONLINE! 🚀**

### 🌐 La tua app è accessibile a:
- **URL:** `https://tua-app-url.ondigitalocean.app`
- **API Docs:** `https://tua-app-url.ondigitalocean.app/docs`
- **Admin:** `https://tua-app-url.ondigitalocean.app/admin`

### 💰 Pronto per monetizzare:
- ✅ **Freemium model** attivo
- ✅ **Stripe billing** funzionante  
- ✅ **GDPR compliant** per mercato EU
- ✅ **Scalabile** per migliaia di utenti

### 📈 Prossimi step business:
1. **🎯 Marketing:** Social media, SEO, content marketing
2. **📧 Email:** Newsletter e automation marketing
3. **📊 Analytics:** Google Analytics, tracking conversioni
4. **🎨 Design:** UI/UX improvements iterativi
5. **🚀 Features:** Nuove funzionalità basate su feedback utenti

---

**🎬 AIVideoMaker Freemium è il tuo business SaaS pronto per il successo! 💰🚀**

*Guida completata - Sistema enterprise production-ready online!*