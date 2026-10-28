DE1 VGA Simulator (Python)
Ce projet est un simulateur graphique de la carte Altera DE1 écrit en Python. Il permet de tester vos entités VHDL

1. Installation
Assurez-vous d'avoir Python 3 installé, puis installez les dépendances requises :

bash


pip install -r requirements.txt


(Si vous êtes sous Linux, tkinter peut nécessiter une installation système : sudo apt install python3-tk)

2. Structure du projet
Votre dossier de travail doit ressembler à ceci :




text
mon_projet/
├── vga_sim.py           # Le simulateur
├── requirements.txt     # Dépendances (numpy, Pillow)
└── vhd/                 # Dossier contenant le matériel
    ├── vga_top.vhd      # Votre entité top-level
    ├── vga_sync.vhd     # Vos autres fichiers VHDL...
    └── config.txt       # Le fichier de configuration (créé automatiquement)



3. Le fichier config.txt
Le fichier vhd/config.txt utilise la syntaxe Quartus (.qsf) pour mapper l'interface graphique Python vers les ports de votre entité VHDL.

Règles de base :
Entité Top : set_global_assignment -name TOP_LEVEL_ENTITY <nom_entite> (sans le .vhd).

Assignation des contrôles : set_location_assignment <NOEUD_PY> -to <PORT_VHDL> # <Label>

<NOEUD_PY> : SW0..SW9, KEY0..KEY3, ou LED0..LED9.

<PORT_VHDL> : Le nom du port dans votre entité.

<Label> (optionnel) : Le texte qui s'affichera sur l'interface (ex: # Reset).

(Remarque : si un bouton ou un switch n'est pas défini dans le config.txt, le simulateur lui donnera automatiquement un nom par défaut, comme SW0).




4. Exemple avec vga_top
Si vous voulez simuler votre design vga_top.vhd (le générateur de motifs), votre fichier vhd/config.txt doit être configuré ainsi :


code:



set_global_assignment -name TOP_LEVEL_ENTITY vga_top

# -- SWITCHES --
set_location_assignment SW0 -to SW(0) # Mode[0]
set_location_assignment SW1 -to SW(1) # Mode[1]

set_location_assignment SW2 -to SW(2) # Color Blue
set_location_assignment SW3 -to SW(3) # Color Green
set_location_assignment SW4 -to SW(4) # Color Red

set_location_assignment SW5 -to SW(5) # Scroll En

set_location_assignment SW8 -to SW(8) # Speed[0]
set_location_assignment SW9 -to SW(9) # Speed[1]

# -- BOUTONS --
set_location_assignment KEY0 -to KEY(0) # Reset (Actif bas)
set_location_assignment KEY1 -to KEY(1) # Freeze (Actif bas)

# -- LEDS --
# L'entité vga_top ne renvoie pas de score, donc on peut 
# mapper les LED sur les interrupteurs pour visualiser leur état
set_location_assignment LED0 -to LEDR(0) # SW0
set_location_assignment LED1 -to LEDR(1) # SW1
set_location_assignment LED2 -to LEDR(2) # SW2




5. Lancement
Une fois le fichier config.txt configuré, lancez simplement le script :




bash


python vga_sim.py


Le simulateur va :

Lire config.txt.

Vérifier que les ports mappés existent bien dans votre fichier .vhd.

Ouvrir la fenêtre avec l'écran VGA et les contrôles avec les bons labels.