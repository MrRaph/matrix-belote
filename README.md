# matrix-belote

Bot Matrix pour jouer à la Belote coinchée (4 joueurs, dont vous et 3 bots).

## Installation

1. Installez Python 3.8+ et Poetry  
2. Clonez :
   ```bash
   git clone https://github.com/MrRaph/matrix-belote.git
   cd matrix-belote
   ```

    Installez les dépendances :

    ```bash
    poetry install
    ```

## Configuration

Définissez les variables d’environnement :

export HOMESERVER=https://matrix.org
export USERNAME=belote-bot
export PASSWORD=monpassword    # OU ACCESS_TOKEN=...
export PREFIX=b!

## Utilisation

```bash
poetry run python main.py
```

Puis, dans une salle Matrix où le bot est invité :

    b!help : affiche l’aide

    b!start : démarre une nouvelle partie

    b!bid <points> <suit> (ex. b!bid 80 hearts) ou b!pass

    b!coinche / b!surcoinche

    b!play <card> (ex. b!play 10S, b!play QH)

    b!hand : affiche votre main

    b!trick : affiche le pli en cours

    b!score : affiche les scores actuels

