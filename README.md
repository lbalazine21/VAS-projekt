**Upute za pokretanje:**
1. Preuzeti cijeli kod unutar ZIP datoteke ili klonirati direktorij na disku.
2. Pozicionirati se unutar radnog direktorija.
3. Unutar terminala upisati komandu ```uv init``` za inicijaliziranje novog Python projekta.
4. Zatim upisati ```source .venv/bin/activate``` za aktiviranje virtualnog Python okruženja.
5. Nakon toga upisati ```spade run``` za pokretanje SPADE servera.
6. Na kraju otvoriti novi terminal i upisati ```uv run main.py``` za pokretanje simulacije.

**Za ispravan rad aplikacije potrebno je instalirati sljedeće dodatke:**
- Python i podrška za virtualna okruženja: ```sudo apt install python3 python3-venv python3-pip -y```
- Alat uv za inicijalizaciju i pokretanje Python projekata: ```curl -LsSf https://astral.sh/uv/install.sh | sh```
- SPADE okvir za višeagentne sustave: ```pip3 install spade```
- XMPP server potreban za rad SPADE okvira: ```sudo apt install ejabberd -y```
