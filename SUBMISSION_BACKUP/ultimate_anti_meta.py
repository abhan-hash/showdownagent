"""
REDLINE Pokemon agent - search-based, standard library only.

Pipeline each turn:
  1. Update memory (foe moves seen/inferred, speed evidence, switch-in turns).
  2. Build a model of every mon (ours from MY_TEAM, foe from portal defaults + evidence).
  3. For each of my legal actions, simulate the turn against a distribution of foe actions
     (priority, speed probability, accuracy, damage rolls, KO thresholds), score the leaf
     with a material + 1v1-race evaluation, and pick the best blend of expected / worst case.
Everything is wrapped so that decide() can never return an illegal action.
"""
import json
import math

DATA = json.loads(r'''{"species":{"Garchomp":{"b":[108,130,95,80,85,102],"t":["Dragon","Ground"],"evs":[0,252,0,0,4,252],"nature":"jolly","ab":["roughskin","sandveil"],"item":"lifeorb","dm":["earthquake","outrage","stoneedge","swordsdance"],"legal":["earthquake","outrage","dragonclaw","stoneedge","rockslide","swordsdance","firefang","ironhead","stealthrock","crunch","poisonjab","dracometeor"]},"Dragonite":{"b":[91,134,95,100,100,80],"t":["Dragon","Flying"],"evs":[0,252,0,0,4,252],"nature":"adamant","ab":["multiscale","innerfocus"],"item":"lumberry","dm":["extremespeed","outrage","earthquake","firepunch"],"legal":["extremespeed","outrage","dragonclaw","earthquake","firepunch","thunderpunch","icespinner","dragondance","roost","hurricane","superpower","ironhead"]},"Tyranitar":{"b":[100,134,110,95,100,61],"t":["Rock","Dark"],"evs":[252,252,0,0,4,0],"nature":"adamant","ab":["sandstream","unnerve"],"item":"leftovers","dm":["stoneedge","crunch","earthquake","icepunch"],"legal":["stoneedge","rockslide","crunch","earthquake","icepunch","firepunch","thunderpunch","stealthrock","dragondance","ironhead","bodyslam","thunderwave"]},"Metagross":{"b":[80,135,130,95,90,70],"t":["Steel","Psychic"],"evs":[252,252,0,0,0,4],"nature":"adamant","ab":["clearbody","lightmetal"],"item":"assaultvest","dm":["meteormash","bulletpunch","earthquake","zenheadbutt"],"legal":["meteormash","bulletpunch","earthquake","zenheadbutt","icepunch","thunderpunch","hammerarm","agility","stealthrock","psychicfangs","explosion","trick"]},"Salamence":{"b":[95,135,80,110,80,100],"t":["Dragon","Flying"],"evs":[0,4,0,252,0,252],"nature":"naive","ab":["intimidate","moxie"],"item":"lifeorb","dm":["dracometeor","flamethrower","earthquake","roost"],"legal":["dracometeor","dragonclaw","outrage","flamethrower","fireblast","earthquake","roost","dragondance","hydropump","hurricane","stoneedge","ironhead"]},"Hydreigon":{"b":[92,105,90,125,90,98],"t":["Dark","Dragon"],"evs":[0,0,0,252,4,252],"nature":"timid","ab":["levitate"],"item":"choicespecs","dm":["darkpulse","dracometeor","flamethrower","flashcannon"],"legal":["darkpulse","dracometeor","dragonpulse","flamethrower","fireblast","flashcannon","earthpower","uturn","roost","nastyplot","focusblast","surf"]},"Dragapult":{"b":[88,120,75,100,75,142],"t":["Dragon","Ghost"],"evs":[0,252,0,0,4,252],"nature":"jolly","ab":["infiltrator","clearbody"],"item":"choiceband","dm":["dragondarts","phantomforce","flamethrower","uturn"],"legal":["dragondarts","phantomforce","shadowball","flamethrower","uturn","thunderbolt","hydropump","psychicfangs","suckerpunch","dragondance","willowisp","dracometeor"]},"Volcarona":{"b":[85,60,65,135,105,100],"t":["Bug","Fire"],"evs":[0,0,0,252,4,252],"nature":"timid","ab":["flamebody","swarm"],"item":"heavydutyboots","dm":["fierydance","bugbuzz","gigadrain","quiverdance"],"legal":["fierydance","fireblast","flamethrower","bugbuzz","gigadrain","quiverdance","psychic","hurricane","roost","willowisp","overheat","morningsun"]},"Lucario":{"b":[70,110,70,115,70,90],"t":["Fighting","Steel"],"evs":[0,252,0,4,0,252],"nature":"jolly","ab":["innerfocus","steadfast","justified"],"item":"lifeorb","dm":["closecombat","meteormash","extremespeed","flashcannon"],"legal":["closecombat","aurasphere","meteormash","flashcannon","extremespeed","swordsdance","icepunch","thunderpunch","bulletpunch","stoneedge","crunch","dragonpulse"]},"Scizor":{"b":[70,130,100,55,80,65],"t":["Bug","Steel"],"evs":[252,252,0,0,4,0],"nature":"adamant","ab":["technician","swarm"],"item":"metalcoat","dm":["bulletpunch","closecombat","swordsdance","uturn"],"legal":["bulletpunch","closecombat","swordsdance","uturn","xscissor","dualwingbeat","knockoff","roost","ironhead","quickattack","trailblaze","defog"]},"Gengar":{"b":[60,65,60,130,75,110],"t":["Ghost","Poison"],"evs":[0,0,0,252,4,252],"nature":"timid","ab":["cursedbody"],"item":"lifeorb","dm":["shadowball","sludgebomb","focusblast","thunderbolt"],"legal":["shadowball","sludgebomb","focusblast","thunderbolt","energyball","psychic","dazzlinggleam","nastyplot","willowisp","destinybond","trick","gigadrain"]},"Gyarados":{"b":[95,125,79,60,100,81],"t":["Water","Flying"],"evs":[0,252,4,0,0,252],"nature":"jolly","ab":["intimidate","moxie"],"item":"leftovers","dm":["waterfall","earthquake","icefang","dragondance"],"legal":["waterfall","earthquake","icefang","dragondance","bounce","crunch","powerwhip","stoneedge","thunderwave","taunt","hydropump","outrage"]},"Charizard":{"b":[78,84,78,109,85,100],"t":["Fire","Flying"],"evs":[0,0,0,252,4,252],"nature":"timid","ab":["blaze","solarpower"],"item":"choicespecs","dm":["flamethrower","airslash","focusblast","dragonpulse"],"legal":["flamethrower","fireblast","airslash","focusblast","dragonpulse","solarbeam","roost","overheat","willowisp","flareblitz","dragondance","earthquake"]},"Blastoise":{"b":[79,83,100,85,105,78],"t":["Water"],"evs":[252,0,0,252,4,0],"nature":"modest","ab":["torrent","raindish"],"item":"leftovers","dm":["hydropump","icebeam","flashcannon","protect"],"legal":["hydropump","surf","icebeam","flashcannon","aurasphere","darkpulse","protect","rapidspin","aquajet","yawn","scald","dragonpulse"]},"Venusaur":{"b":[80,82,83,100,100,80],"t":["Grass","Poison"],"evs":[252,0,0,252,4,0],"nature":"modest","ab":["overgrow","chlorophyll"],"item":"blacksludge","dm":["gigadrain","sludgebomb","earthpower","sleeppowder"],"legal":["gigadrain","energyball","sludgebomb","earthpower","sleeppowder","leechseed","synthesis","growth","weatherball","knockoff","leafstorm","toxic"]},"Arcanine":{"b":[90,110,80,100,80,95],"t":["Fire"],"evs":[252,252,0,0,0,4],"nature":"adamant","ab":["intimidate","flashfire","justified"],"item":"heavydutyboots","dm":["flareblitz","extremespeed","wildcharge","willowisp"],"legal":["flareblitz","extremespeed","wildcharge","willowisp","closecombat","morningsun","crunch","playrough","flamethrower","psychicfangs","teleport","snarl"]},"Excadrill":{"b":[110,135,60,50,65,88],"t":["Ground","Steel"],"evs":[0,252,0,0,4,252],"nature":"jolly","ab":["moldbreaker","sandrush","sandforce"],"item":"focussash","dm":["earthquake","ironhead","rockslide","swordsdance"],"legal":["earthquake","ironhead","rockslide","swordsdance","rapidspin","stealthrock","shadowclaw","brickbreak","xscissor","drillrun","highhorsepower","poisonjab"]},"Togekiss":{"b":[85,50,95,120,115,80],"t":["Fairy","Flying"],"evs":[252,0,0,4,0,252],"nature":"timid","ab":["serenegrace","superluck"],"item":"leftovers","dm":["airslash","dazzlinggleam","aurasphere","roost"],"legal":["airslash","dazzlinggleam","aurasphere","roost","nastyplot","flamethrower","thunderwave","psychic","wish","protect","ancientpower","shadowball"]},"Snorlax":{"b":[160,110,65,65,110,30],"t":["Normal"],"evs":[252,0,4,0,252,0],"nature":"careful","ab":["thickfat","immunity"],"item":"leftovers","dm":["bodyslam","earthquake","crunch","rest"],"legal":["bodyslam","earthquake","crunch","rest","sleeptalk","curse","heavyslam","firepunch","icepunch","darkestlariat","bodypress","gigaimpact"]},"Alakazam":{"b":[55,50,45,135,95,120],"t":["Psychic"],"evs":[4,0,0,252,0,252],"nature":"timid","ab":["magicguard","synchronize","innerfocus"],"item":"lifeorb","dm":["psychic","shadowball","focusblast","energyball"],"legal":["psychic","psyshock","shadowball","focusblast","energyball","dazzlinggleam","nastyplot","recover","thunderwave","trick","calmmind","chargebeam"]},"Lapras":{"b":[130,85,80,85,95,60],"t":["Water","Ice"],"evs":[252,0,0,252,4,0],"nature":"modest","ab":["waterabsorb","shellarmor"],"item":"leftovers","dm":["freezedry","hydropump","thunderbolt","icebeam"],"legal":["freezedry","hydropump","surf","thunderbolt","icebeam","protect","bodyslam","iceshard","dragonpulse","psychic","perishsong","roar"]},"Corviknight":{"b":[98,87,105,53,85,67],"t":["Flying","Steel"],"evs":[252,0,252,0,4,0],"nature":"impish","ab":["mirrorarmor","pressure"],"item":"leftovers","dm":["bravebird","bodypress","roost","irondefense"],"legal":["bravebird","bodypress","irondefense","roost","uturn","defog","ironhead","taunt","tailwind","bulkup","heavyslam","drillpeck"]},"Ferrothorn":{"b":[74,94,131,54,116,20],"t":["Grass","Steel"],"evs":[252,0,252,0,4,0],"nature":"relaxed","ab":["ironbarbs"],"item":"leftovers","dm":["powerwhip","gyroball","leechseed","protect"],"legal":["powerwhip","gyroball","leechseed","protect","stealthrock","spikes","knockoff","thunderwave","bodypress","ironhead","seedbomb","bulldoze"]},"Greninja":{"b":[72,95,67,103,71,122],"t":["Water","Dark"],"evs":[4,0,0,252,0,252],"nature":"timid","ab":["protean","torrent"],"item":"lifeorb","dm":["hydropump","darkpulse","icebeam","uturn"],"legal":["hydropump","darkpulse","icebeam","uturn","watershuriken","gunkshot","lowkick","spikes","toxicspikes","grassknot","extrasensory","shadowsneak"]}},"moves":{"10000000voltthunderbolt":{"n":"10,000,000 Volt Thunderbolt","t":"Electric","c":"S","bp":195,"a":101,"p":0},"absorb":{"n":"Absorb","t":"Grass","c":"S","bp":20,"a":100,"p":0},"accelerock":{"n":"Accelerock","t":"Rock","c":"P","bp":40,"a":100,"p":1,"ct":true},"acid":{"n":"Acid","t":"Poison","c":"S","bp":40,"a":100,"p":0},"acidarmor":{"n":"Acid Armor","t":"Poison","c":"T","bp":0,"a":101,"p":0},"aciddownpour":{"n":"Acid Downpour","t":"Poison","c":"P","bp":1,"a":101,"p":0},"acidspray":{"n":"Acid Spray","t":"Poison","c":"S","bp":40,"a":100,"p":0},"acrobatics":{"n":"Acrobatics","t":"Flying","c":"P","bp":55,"a":100,"p":0,"ct":true},"acupressure":{"n":"Acupressure","t":"Normal","c":"T","bp":0,"a":101,"p":0},"aerialace":{"n":"Aerial Ace","t":"Flying","c":"P","bp":60,"a":101,"p":0,"ct":true},"aeroblast":{"n":"Aeroblast","t":"Flying","c":"S","bp":100,"a":95,"p":0},"afteryou":{"n":"After You","t":"Normal","c":"T","bp":0,"a":101,"p":0},"agility":{"n":"Agility","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"aircutter":{"n":"Air Cutter","t":"Flying","c":"S","bp":60,"a":95,"p":0},"airslash":{"n":"Air Slash","t":"Flying","c":"S","bp":75,"a":95,"p":0},"alloutpummeling":{"n":"All-Out Pummeling","t":"Fighting","c":"P","bp":1,"a":101,"p":0},"alluringvoice":{"n":"Alluring Voice","t":"Fairy","c":"S","bp":80,"a":100,"p":0},"allyswitch":{"n":"Ally Switch","t":"Psychic","c":"T","bp":0,"a":101,"p":2},"amnesia":{"n":"Amnesia","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"anchorshot":{"n":"Anchor Shot","t":"Steel","c":"P","bp":80,"a":100,"p":0,"ct":true},"ancientpower":{"n":"Ancient Power","t":"Rock","c":"S","bp":60,"a":100,"p":0},"appleacid":{"n":"Apple Acid","t":"Grass","c":"S","bp":80,"a":100,"p":0},"aquacutter":{"n":"Aqua Cutter","t":"Water","c":"P","bp":70,"a":100,"p":0},"aquajet":{"n":"Aqua Jet","t":"Water","c":"P","bp":40,"a":100,"p":1,"ct":true},"aquaring":{"n":"Aqua Ring","t":"Water","c":"T","bp":0,"a":101,"p":0},"aquastep":{"n":"Aqua Step","t":"Water","c":"P","bp":80,"a":100,"p":0,"ct":true},"aquatail":{"n":"Aqua Tail","t":"Water","c":"P","bp":90,"a":90,"p":0,"ct":true},"armorcannon":{"n":"Armor Cannon","t":"Fire","c":"S","bp":120,"a":100,"p":0,"sb":{"def":-1,"spd":-1}},"armthrust":{"n":"Arm Thrust","t":"Fighting","c":"P","bp":15,"a":100,"p":0,"mh":[2,5],"ct":true},"aromatherapy":{"n":"Aromatherapy","t":"Grass","c":"T","bp":0,"a":101,"p":0},"aromaticmist":{"n":"Aromatic Mist","t":"Fairy","c":"T","bp":0,"a":101,"p":0},"assist":{"n":"Assist","t":"Normal","c":"T","bp":0,"a":101,"p":0},"assurance":{"n":"Assurance","t":"Dark","c":"P","bp":60,"a":100,"p":0,"ct":true},"astonish":{"n":"Astonish","t":"Ghost","c":"P","bp":30,"a":100,"p":0,"ct":true},"astralbarrage":{"n":"Astral Barrage","t":"Ghost","c":"S","bp":120,"a":100,"p":0},"attackorder":{"n":"Attack Order","t":"Bug","c":"P","bp":90,"a":100,"p":0},"attract":{"n":"Attract","t":"Normal","c":"T","bp":0,"a":100,"p":0},"aurasphere":{"n":"Aura Sphere","t":"Fighting","c":"S","bp":80,"a":101,"p":0},"aurawheel":{"n":"Aura Wheel","t":"Electric","c":"P","bp":110,"a":100,"p":0},"aurorabeam":{"n":"Aurora Beam","t":"Ice","c":"S","bp":65,"a":100,"p":0},"auroraveil":{"n":"Aurora Veil","t":"Ice","c":"T","bp":0,"a":101,"p":0},"autotomize":{"n":"Autotomize","t":"Steel","c":"T","bp":0,"a":101,"p":0},"avalanche":{"n":"Avalanche","t":"Ice","c":"P","bp":60,"a":100,"p":-4,"ct":true},"axekick":{"n":"Axe Kick","t":"Fighting","c":"P","bp":120,"a":90,"p":0,"ct":true},"babydolleyes":{"n":"Baby-Doll Eyes","t":"Fairy","c":"T","bp":0,"a":100,"p":1},"baddybad":{"n":"Baddy Bad","t":"Dark","c":"S","bp":80,"a":95,"p":0},"banefulbunker":{"n":"Baneful Bunker","t":"Poison","c":"T","bp":0,"a":101,"p":4},"barbbarrage":{"n":"Barb Barrage","t":"Poison","c":"P","bp":60,"a":100,"p":0},"barrage":{"n":"Barrage","t":"Normal","c":"P","bp":15,"a":85,"p":0,"mh":[2,5]},"barrier":{"n":"Barrier","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"batonpass":{"n":"Baton Pass","t":"Normal","c":"T","bp":0,"a":101,"p":0},"beakblast":{"n":"Beak Blast","t":"Flying","c":"P","bp":100,"a":100,"p":-3},"beatup":{"n":"Beat Up","t":"Dark","c":"P","bp":0,"a":100,"p":0},"behemothbash":{"n":"Behemoth Bash","t":"Steel","c":"P","bp":100,"a":100,"p":0,"ct":true},"behemothblade":{"n":"Behemoth Blade","t":"Steel","c":"P","bp":100,"a":100,"p":0,"ct":true},"belch":{"n":"Belch","t":"Poison","c":"S","bp":120,"a":90,"p":0},"bellydrum":{"n":"Belly Drum","t":"Normal","c":"T","bp":0,"a":101,"p":0},"bestow":{"n":"Bestow","t":"Normal","c":"T","bp":0,"a":101,"p":0},"bide":{"n":"Bide","t":"Normal","c":"P","bp":0,"a":101,"p":1,"ct":true},"bind":{"n":"Bind","t":"Normal","c":"P","bp":15,"a":85,"p":0,"ct":true},"bite":{"n":"Bite","t":"Dark","c":"P","bp":60,"a":100,"p":0,"ct":true},"bitterblade":{"n":"Bitter Blade","t":"Fire","c":"P","bp":90,"a":100,"p":0,"ct":true},"bittermalice":{"n":"Bitter Malice","t":"Ghost","c":"S","bp":75,"a":100,"p":0},"blackholeeclipse":{"n":"Black Hole Eclipse","t":"Dark","c":"P","bp":1,"a":101,"p":0},"blastburn":{"n":"Blast Burn","t":"Fire","c":"S","bp":150,"a":90,"p":0},"blazekick":{"n":"Blaze Kick","t":"Fire","c":"P","bp":85,"a":90,"p":0,"ct":true},"blazingtorque":{"n":"Blazing Torque","t":"Fire","c":"P","bp":80,"a":100,"p":0},"bleakwindstorm":{"n":"Bleakwind Storm","t":"Flying","c":"S","bp":100,"a":80,"p":0},"blizzard":{"n":"Blizzard","t":"Ice","c":"S","bp":110,"a":70,"p":0},"block":{"n":"Block","t":"Normal","c":"T","bp":0,"a":101,"p":0},"bloodmoon":{"n":"Blood Moon","t":"Normal","c":"S","bp":140,"a":100,"p":0},"bloomdoom":{"n":"Bloom Doom","t":"Grass","c":"P","bp":1,"a":101,"p":0},"blueflare":{"n":"Blue Flare","t":"Fire","c":"S","bp":130,"a":85,"p":0},"bodypress":{"n":"Body Press","t":"Fighting","c":"P","bp":80,"a":100,"p":0,"bodypress":true,"ct":true},"bodyslam":{"n":"Body Slam","t":"Normal","c":"P","bp":85,"a":100,"p":0,"ct":true},"boltbeak":{"n":"Bolt Beak","t":"Electric","c":"P","bp":85,"a":100,"p":0,"ct":true},"boltstrike":{"n":"Bolt Strike","t":"Electric","c":"P","bp":130,"a":85,"p":0,"ct":true},"boneclub":{"n":"Bone Club","t":"Ground","c":"P","bp":65,"a":85,"p":0},"bonemerang":{"n":"Bonemerang","t":"Ground","c":"P","bp":50,"a":90,"p":0,"mh":2},"bonerush":{"n":"Bone Rush","t":"Ground","c":"P","bp":25,"a":90,"p":0,"mh":[2,5]},"boomburst":{"n":"Boomburst","t":"Normal","c":"S","bp":140,"a":100,"p":0},"bounce":{"n":"Bounce","t":"Flying","c":"P","bp":85,"a":85,"p":0,"ct":true},"bouncybubble":{"n":"Bouncy Bubble","t":"Water","c":"S","bp":60,"a":100,"p":0},"branchpoke":{"n":"Branch Poke","t":"Grass","c":"P","bp":40,"a":100,"p":0,"ct":true},"bravebird":{"n":"Brave Bird","t":"Flying","c":"P","bp":120,"a":100,"p":0,"ct":true,"rc":[33,100]},"breakingswipe":{"n":"Breaking Swipe","t":"Dragon","c":"P","bp":60,"a":100,"p":0,"ct":true},"breakneckblitz":{"n":"Breakneck Blitz","t":"Normal","c":"P","bp":1,"a":101,"p":0},"brickbreak":{"n":"Brick Break","t":"Fighting","c":"P","bp":75,"a":100,"p":0,"ct":true},"brine":{"n":"Brine","t":"Water","c":"S","bp":65,"a":100,"p":0},"brutalswing":{"n":"Brutal Swing","t":"Dark","c":"P","bp":60,"a":100,"p":0,"ct":true},"bubble":{"n":"Bubble","t":"Water","c":"S","bp":40,"a":100,"p":0},"bubblebeam":{"n":"Bubble Beam","t":"Water","c":"S","bp":65,"a":100,"p":0},"bugbite":{"n":"Bug Bite","t":"Bug","c":"P","bp":60,"a":100,"p":0,"ct":true},"bugbuzz":{"n":"Bug Buzz","t":"Bug","c":"S","bp":90,"a":100,"p":0},"bulkup":{"n":"Bulk Up","t":"Fighting","c":"T","bp":0,"a":101,"p":0},"bulldoze":{"n":"Bulldoze","t":"Ground","c":"P","bp":60,"a":100,"p":0},"bulletpunch":{"n":"Bullet Punch","t":"Steel","c":"P","bp":40,"a":100,"p":1,"ct":true},"bulletseed":{"n":"Bullet Seed","t":"Grass","c":"P","bp":25,"a":100,"p":0,"mh":[2,5]},"burningbulwark":{"n":"Burning Bulwark","t":"Fire","c":"T","bp":0,"a":101,"p":4},"burningjealousy":{"n":"Burning Jealousy","t":"Fire","c":"S","bp":70,"a":100,"p":0},"burnup":{"n":"Burn Up","t":"Fire","c":"S","bp":130,"a":100,"p":0},"buzzybuzz":{"n":"Buzzy Buzz","t":"Electric","c":"S","bp":60,"a":100,"p":0},"calmmind":{"n":"Calm Mind","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"camouflage":{"n":"Camouflage","t":"Normal","c":"T","bp":0,"a":101,"p":0},"captivate":{"n":"Captivate","t":"Normal","c":"T","bp":0,"a":100,"p":0},"catastropika":{"n":"Catastropika","t":"Electric","c":"P","bp":210,"a":101,"p":0,"ct":true},"ceaselessedge":{"n":"Ceaseless Edge","t":"Dark","c":"P","bp":65,"a":90,"p":0,"ct":true},"celebrate":{"n":"Celebrate","t":"Normal","c":"T","bp":0,"a":101,"p":0},"charge":{"n":"Charge","t":"Electric","c":"T","bp":0,"a":101,"p":0},"chargebeam":{"n":"Charge Beam","t":"Electric","c":"S","bp":50,"a":90,"p":0},"charm":{"n":"Charm","t":"Fairy","c":"T","bp":0,"a":100,"p":0},"chatter":{"n":"Chatter","t":"Flying","c":"S","bp":65,"a":100,"p":0},"chillingwater":{"n":"Chilling Water","t":"Water","c":"S","bp":50,"a":100,"p":0},"chillyreception":{"n":"Chilly Reception","t":"Ice","c":"T","bp":0,"a":101,"p":0},"chipaway":{"n":"Chip Away","t":"Normal","c":"P","bp":70,"a":100,"p":0,"ct":true},"chloroblast":{"n":"Chloroblast","t":"Grass","c":"S","bp":150,"a":95,"p":0},"circlethrow":{"n":"Circle Throw","t":"Fighting","c":"P","bp":60,"a":90,"p":-6,"ct":true},"clamp":{"n":"Clamp","t":"Water","c":"P","bp":35,"a":85,"p":0,"ct":true},"clangingscales":{"n":"Clanging Scales","t":"Dragon","c":"S","bp":110,"a":100,"p":0},"clangoroussoul":{"n":"Clangorous Soul","t":"Dragon","c":"T","bp":0,"a":100,"p":0},"clangoroussoulblaze":{"n":"Clangorous Soulblaze","t":"Dragon","c":"S","bp":185,"a":101,"p":0},"clearsmog":{"n":"Clear Smog","t":"Poison","c":"S","bp":50,"a":101,"p":0},"closecombat":{"n":"Close Combat","t":"Fighting","c":"P","bp":120,"a":100,"p":0,"ct":true,"sb":{"def":-1,"spd":-1}},"coaching":{"n":"Coaching","t":"Fighting","c":"T","bp":0,"a":101,"p":0},"coil":{"n":"Coil","t":"Poison","c":"T","bp":0,"a":101,"p":0},"collisioncourse":{"n":"Collision Course","t":"Fighting","c":"P","bp":100,"a":100,"p":0,"ct":true},"combattorque":{"n":"Combat Torque","t":"Fighting","c":"P","bp":100,"a":100,"p":0},"cometpunch":{"n":"Comet Punch","t":"Normal","c":"P","bp":18,"a":85,"p":0,"mh":[2,5],"ct":true},"comeuppance":{"n":"Comeuppance","t":"Dark","c":"P","bp":0,"a":100,"p":0,"ct":true},"confide":{"n":"Confide","t":"Normal","c":"T","bp":0,"a":101,"p":0},"confuseray":{"n":"Confuse Ray","t":"Ghost","c":"T","bp":0,"a":100,"p":0},"confusion":{"n":"Confusion","t":"Psychic","c":"S","bp":50,"a":100,"p":0},"constrict":{"n":"Constrict","t":"Normal","c":"P","bp":10,"a":100,"p":0,"ct":true},"continentalcrush":{"n":"Continental Crush","t":"Rock","c":"P","bp":1,"a":101,"p":0},"conversion":{"n":"Conversion","t":"Normal","c":"T","bp":0,"a":101,"p":0},"conversion2":{"n":"Conversion 2","t":"Normal","c":"T","bp":0,"a":101,"p":0},"copycat":{"n":"Copycat","t":"Normal","c":"T","bp":0,"a":101,"p":0},"coreenforcer":{"n":"Core Enforcer","t":"Dragon","c":"S","bp":100,"a":100,"p":0},"corkscrewcrash":{"n":"Corkscrew Crash","t":"Steel","c":"P","bp":1,"a":101,"p":0},"corrosivegas":{"n":"Corrosive Gas","t":"Poison","c":"T","bp":0,"a":100,"p":0},"cosmicpower":{"n":"Cosmic Power","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"cottonguard":{"n":"Cotton Guard","t":"Grass","c":"T","bp":0,"a":101,"p":0},"cottonspore":{"n":"Cotton Spore","t":"Grass","c":"T","bp":0,"a":100,"p":0},"counter":{"n":"Counter","t":"Fighting","c":"P","bp":0,"a":100,"p":-5,"ct":true},"courtchange":{"n":"Court Change","t":"Normal","c":"T","bp":0,"a":100,"p":0},"covet":{"n":"Covet","t":"Normal","c":"P","bp":60,"a":100,"p":0,"ct":true},"crabhammer":{"n":"Crabhammer","t":"Water","c":"P","bp":100,"a":90,"p":0,"ct":true},"craftyshield":{"n":"Crafty Shield","t":"Fairy","c":"T","bp":0,"a":101,"p":3},"crosschop":{"n":"Cross Chop","t":"Fighting","c":"P","bp":100,"a":80,"p":0,"ct":true},"crosspoison":{"n":"Cross Poison","t":"Poison","c":"P","bp":70,"a":100,"p":0,"ct":true},"crunch":{"n":"Crunch","t":"Dark","c":"P","bp":80,"a":100,"p":0,"ct":true},"crushclaw":{"n":"Crush Claw","t":"Normal","c":"P","bp":75,"a":95,"p":0,"ct":true},"crushgrip":{"n":"Crush Grip","t":"Normal","c":"P","bp":0,"a":100,"p":0,"ct":true},"curse":{"n":"Curse","t":"Ghost","c":"T","bp":0,"a":101,"p":0},"cut":{"n":"Cut","t":"Normal","c":"P","bp":50,"a":95,"p":0,"ct":true},"darkestlariat":{"n":"Darkest Lariat","t":"Dark","c":"P","bp":85,"a":100,"p":0,"ct":true},"darkpulse":{"n":"Dark Pulse","t":"Dark","c":"S","bp":80,"a":100,"p":0},"darkvoid":{"n":"Dark Void","t":"Dark","c":"T","bp":0,"a":50,"p":0},"dazzlinggleam":{"n":"Dazzling Gleam","t":"Fairy","c":"S","bp":80,"a":100,"p":0},"decorate":{"n":"Decorate","t":"Fairy","c":"T","bp":0,"a":101,"p":0},"defendorder":{"n":"Defend Order","t":"Bug","c":"T","bp":0,"a":101,"p":0},"defensecurl":{"n":"Defense Curl","t":"Normal","c":"T","bp":0,"a":101,"p":0},"defog":{"n":"Defog","t":"Flying","c":"T","bp":0,"a":101,"p":0},"destinybond":{"n":"Destiny Bond","t":"Ghost","c":"T","bp":0,"a":101,"p":0},"detect":{"n":"Detect","t":"Fighting","c":"T","bp":0,"a":101,"p":4},"devastatingdrake":{"n":"Devastating Drake","t":"Dragon","c":"P","bp":1,"a":101,"p":0},"diamondstorm":{"n":"Diamond Storm","t":"Rock","c":"P","bp":100,"a":95,"p":0,"sb":{"def":2}},"dig":{"n":"Dig","t":"Ground","c":"P","bp":80,"a":100,"p":0,"ct":true},"direclaw":{"n":"Dire Claw","t":"Poison","c":"P","bp":80,"a":100,"p":0,"ct":true},"disable":{"n":"Disable","t":"Normal","c":"T","bp":0,"a":100,"p":0},"disarmingvoice":{"n":"Disarming Voice","t":"Fairy","c":"S","bp":40,"a":101,"p":0},"discharge":{"n":"Discharge","t":"Electric","c":"S","bp":80,"a":100,"p":0},"dive":{"n":"Dive","t":"Water","c":"P","bp":80,"a":100,"p":0,"ct":true},"dizzypunch":{"n":"Dizzy Punch","t":"Normal","c":"P","bp":70,"a":100,"p":0,"ct":true},"doodle":{"n":"Doodle","t":"Normal","c":"T","bp":0,"a":100,"p":0},"doomdesire":{"n":"Doom Desire","t":"Steel","c":"S","bp":140,"a":100,"p":0},"doubleedge":{"n":"Double-Edge","t":"Normal","c":"P","bp":120,"a":100,"p":0,"ct":true,"rc":[33,100]},"doublehit":{"n":"Double Hit","t":"Normal","c":"P","bp":35,"a":90,"p":0,"mh":2,"ct":true},"doubleironbash":{"n":"Double Iron Bash","t":"Steel","c":"P","bp":60,"a":100,"p":0,"mh":2,"ct":true},"doublekick":{"n":"Double Kick","t":"Fighting","c":"P","bp":30,"a":100,"p":0,"mh":2,"ct":true},"doubleshock":{"n":"Double Shock","t":"Electric","c":"P","bp":120,"a":100,"p":0,"ct":true},"doubleslap":{"n":"Double Slap","t":"Normal","c":"P","bp":15,"a":85,"p":0,"mh":[2,5],"ct":true},"doubleteam":{"n":"Double Team","t":"Normal","c":"T","bp":0,"a":101,"p":0},"dracometeor":{"n":"Draco Meteor","t":"Dragon","c":"S","bp":130,"a":90,"p":0,"sb":{"spa":-2}},"dragonascent":{"n":"Dragon Ascent","t":"Flying","c":"P","bp":120,"a":100,"p":0,"ct":true,"sb":{"def":-1,"spd":-1}},"dragonbreath":{"n":"Dragon Breath","t":"Dragon","c":"S","bp":60,"a":100,"p":0},"dragoncheer":{"n":"Dragon Cheer","t":"Dragon","c":"T","bp":0,"a":101,"p":0},"dragonclaw":{"n":"Dragon Claw","t":"Dragon","c":"P","bp":80,"a":100,"p":0,"ct":true},"dragondance":{"n":"Dragon Dance","t":"Dragon","c":"T","bp":0,"a":101,"p":0},"dragondarts":{"n":"Dragon Darts","t":"Dragon","c":"P","bp":50,"a":100,"p":0,"mh":2},"dragonenergy":{"n":"Dragon Energy","t":"Dragon","c":"S","bp":150,"a":100,"p":0},"dragonhammer":{"n":"Dragon Hammer","t":"Dragon","c":"P","bp":90,"a":100,"p":0,"ct":true},"dragonpulse":{"n":"Dragon Pulse","t":"Dragon","c":"S","bp":85,"a":100,"p":0},"dragonrage":{"n":"Dragon Rage","t":"Dragon","c":"S","bp":0,"a":100,"p":0},"dragonrush":{"n":"Dragon Rush","t":"Dragon","c":"P","bp":100,"a":75,"p":0,"ct":true},"dragontail":{"n":"Dragon Tail","t":"Dragon","c":"P","bp":60,"a":90,"p":-6,"ct":true},"drainingkiss":{"n":"Draining Kiss","t":"Fairy","c":"S","bp":50,"a":100,"p":0,"ct":true},"drainpunch":{"n":"Drain Punch","t":"Fighting","c":"P","bp":75,"a":100,"p":0,"ct":true},"dreameater":{"n":"Dream Eater","t":"Psychic","c":"S","bp":100,"a":100,"p":0},"drillpeck":{"n":"Drill Peck","t":"Flying","c":"P","bp":80,"a":100,"p":0,"ct":true},"drillrun":{"n":"Drill Run","t":"Ground","c":"P","bp":80,"a":95,"p":0,"ct":true},"drumbeating":{"n":"Drum Beating","t":"Grass","c":"P","bp":80,"a":100,"p":0},"dualchop":{"n":"Dual Chop","t":"Dragon","c":"P","bp":40,"a":90,"p":0,"mh":2,"ct":true},"dualwingbeat":{"n":"Dual Wingbeat","t":"Flying","c":"P","bp":40,"a":90,"p":0,"mh":2,"ct":true},"dynamaxcannon":{"n":"Dynamax Cannon","t":"Dragon","c":"S","bp":100,"a":100,"p":0},"dynamicpunch":{"n":"Dynamic Punch","t":"Fighting","c":"P","bp":100,"a":50,"p":0,"ct":true},"earthpower":{"n":"Earth Power","t":"Ground","c":"S","bp":90,"a":100,"p":0},"earthquake":{"n":"Earthquake","t":"Ground","c":"P","bp":100,"a":100,"p":0},"echoedvoice":{"n":"Echoed Voice","t":"Normal","c":"S","bp":40,"a":100,"p":0},"eerieimpulse":{"n":"Eerie Impulse","t":"Electric","c":"T","bp":0,"a":100,"p":0},"eeriespell":{"n":"Eerie Spell","t":"Psychic","c":"S","bp":80,"a":100,"p":0},"eggbomb":{"n":"Egg Bomb","t":"Normal","c":"P","bp":100,"a":75,"p":0},"electricterrain":{"n":"Electric Terrain","t":"Electric","c":"T","bp":0,"a":101,"p":0},"electrify":{"n":"Electrify","t":"Electric","c":"T","bp":0,"a":101,"p":0},"electroball":{"n":"Electro Ball","t":"Electric","c":"S","bp":0,"a":100,"p":0},"electrodrift":{"n":"Electro Drift","t":"Electric","c":"S","bp":100,"a":100,"p":0,"ct":true},"electroshot":{"n":"Electro Shot","t":"Electric","c":"S","bp":130,"a":100,"p":0},"electroweb":{"n":"Electroweb","t":"Electric","c":"S","bp":55,"a":95,"p":0},"embargo":{"n":"Embargo","t":"Dark","c":"T","bp":0,"a":100,"p":0},"ember":{"n":"Ember","t":"Fire","c":"S","bp":40,"a":100,"p":0},"encore":{"n":"Encore","t":"Normal","c":"T","bp":0,"a":100,"p":0},"endeavor":{"n":"Endeavor","t":"Normal","c":"P","bp":0,"a":100,"p":0,"ct":true},"endure":{"n":"Endure","t":"Normal","c":"T","bp":0,"a":101,"p":4},"energyball":{"n":"Energy Ball","t":"Grass","c":"S","bp":90,"a":100,"p":0},"entrainment":{"n":"Entrainment","t":"Normal","c":"T","bp":0,"a":100,"p":0},"eruption":{"n":"Eruption","t":"Fire","c":"S","bp":150,"a":100,"p":0},"esperwing":{"n":"Esper Wing","t":"Psychic","c":"S","bp":80,"a":100,"p":0},"eternabeam":{"n":"Eternabeam","t":"Dragon","c":"S","bp":160,"a":90,"p":0},"expandingforce":{"n":"Expanding Force","t":"Psychic","c":"S","bp":80,"a":100,"p":0},"explosion":{"n":"Explosion","t":"Normal","c":"P","bp":250,"a":100,"p":0},"extrasensory":{"n":"Extrasensory","t":"Psychic","c":"S","bp":80,"a":100,"p":0},"extremeevoboost":{"n":"Extreme Evoboost","t":"Normal","c":"T","bp":0,"a":101,"p":0},"extremespeed":{"n":"Extreme Speed","t":"Normal","c":"P","bp":80,"a":100,"p":2,"ct":true},"facade":{"n":"Facade","t":"Normal","c":"P","bp":70,"a":100,"p":0,"cond":"facade","ct":true},"fairylock":{"n":"Fairy Lock","t":"Fairy","c":"T","bp":0,"a":101,"p":0},"fairywind":{"n":"Fairy Wind","t":"Fairy","c":"S","bp":40,"a":100,"p":0},"fakeout":{"n":"Fake Out","t":"Normal","c":"P","bp":40,"a":100,"p":3,"first":true,"ct":true},"faketears":{"n":"Fake Tears","t":"Dark","c":"T","bp":0,"a":100,"p":0},"falsesurrender":{"n":"False Surrender","t":"Dark","c":"P","bp":80,"a":101,"p":0,"ct":true},"falseswipe":{"n":"False Swipe","t":"Normal","c":"P","bp":40,"a":100,"p":0,"ct":true},"featherdance":{"n":"Feather Dance","t":"Flying","c":"T","bp":0,"a":100,"p":0},"feint":{"n":"Feint","t":"Normal","c":"P","bp":30,"a":100,"p":2},"feintattack":{"n":"Feint Attack","t":"Dark","c":"P","bp":60,"a":101,"p":0,"ct":true},"fellstinger":{"n":"Fell Stinger","t":"Bug","c":"P","bp":50,"a":100,"p":0,"ct":true},"ficklebeam":{"n":"Fickle Beam","t":"Dragon","c":"S","bp":80,"a":100,"p":0},"fierydance":{"n":"Fiery Dance","t":"Fire","c":"S","bp":80,"a":100,"p":0},"fierywrath":{"n":"Fiery Wrath","t":"Dark","c":"S","bp":90,"a":100,"p":0},"filletaway":{"n":"Fillet Away","t":"Normal","c":"T","bp":0,"a":101,"p":0},"finalgambit":{"n":"Final Gambit","t":"Fighting","c":"S","bp":0,"a":100,"p":0},"fireblast":{"n":"Fire Blast","t":"Fire","c":"S","bp":110,"a":85,"p":0},"firefang":{"n":"Fire Fang","t":"Fire","c":"P","bp":65,"a":95,"p":0,"ct":true},"firelash":{"n":"Fire Lash","t":"Fire","c":"P","bp":80,"a":100,"p":0,"ct":true},"firepledge":{"n":"Fire Pledge","t":"Fire","c":"S","bp":80,"a":100,"p":0},"firepunch":{"n":"Fire Punch","t":"Fire","c":"P","bp":75,"a":100,"p":0,"ct":true},"firespin":{"n":"Fire Spin","t":"Fire","c":"S","bp":35,"a":85,"p":0},"firstimpression":{"n":"First Impression","t":"Bug","c":"P","bp":90,"a":100,"p":2,"first":true,"ct":true},"fishiousrend":{"n":"Fishious Rend","t":"Water","c":"P","bp":85,"a":100,"p":0,"ct":true},"fissure":{"n":"Fissure","t":"Ground","c":"P","bp":0,"a":30,"p":0},"flail":{"n":"Flail","t":"Normal","c":"P","bp":0,"a":100,"p":0,"ct":true},"flameburst":{"n":"Flame Burst","t":"Fire","c":"S","bp":70,"a":100,"p":0},"flamecharge":{"n":"Flame Charge","t":"Fire","c":"P","bp":50,"a":100,"p":0,"ct":true},"flamethrower":{"n":"Flamethrower","t":"Fire","c":"S","bp":90,"a":100,"p":0},"flamewheel":{"n":"Flame Wheel","t":"Fire","c":"P","bp":60,"a":100,"p":0,"ct":true},"flareblitz":{"n":"Flare Blitz","t":"Fire","c":"P","bp":120,"a":100,"p":0,"ct":true,"rc":[33,100]},"flash":{"n":"Flash","t":"Normal","c":"T","bp":0,"a":100,"p":0},"flashcannon":{"n":"Flash Cannon","t":"Steel","c":"S","bp":80,"a":100,"p":0},"flatter":{"n":"Flatter","t":"Dark","c":"T","bp":0,"a":100,"p":0},"fleurcannon":{"n":"Fleur Cannon","t":"Fairy","c":"S","bp":130,"a":90,"p":0,"sb":{"spa":-2}},"fling":{"n":"Fling","t":"Dark","c":"P","bp":0,"a":100,"p":0},"flipturn":{"n":"Flip Turn","t":"Water","c":"P","bp":60,"a":100,"p":0,"ct":true},"floatyfall":{"n":"Floaty Fall","t":"Flying","c":"P","bp":90,"a":95,"p":0,"ct":true},"floralhealing":{"n":"Floral Healing","t":"Fairy","c":"T","bp":0,"a":101,"p":0},"flowershield":{"n":"Flower Shield","t":"Fairy","c":"T","bp":0,"a":101,"p":0},"flowertrick":{"n":"Flower Trick","t":"Grass","c":"P","bp":70,"a":101,"p":0},"fly":{"n":"Fly","t":"Flying","c":"P","bp":90,"a":95,"p":0,"ct":true},"flyingpress":{"n":"Flying Press","t":"Fighting","c":"P","bp":100,"a":95,"p":0,"ct":true},"focusblast":{"n":"Focus Blast","t":"Fighting","c":"S","bp":120,"a":70,"p":0},"focusenergy":{"n":"Focus Energy","t":"Normal","c":"T","bp":0,"a":101,"p":0},"focuspunch":{"n":"Focus Punch","t":"Fighting","c":"P","bp":150,"a":100,"p":-3,"ct":true},"followme":{"n":"Follow Me","t":"Normal","c":"T","bp":0,"a":101,"p":2},"forcepalm":{"n":"Force Palm","t":"Fighting","c":"P","bp":60,"a":100,"p":0,"ct":true},"foresight":{"n":"Foresight","t":"Normal","c":"T","bp":0,"a":101,"p":0},"forestscurse":{"n":"Forest's Curse","t":"Grass","c":"T","bp":0,"a":100,"p":0},"foulplay":{"n":"Foul Play","t":"Dark","c":"P","bp":95,"a":100,"p":0,"foulplay":true,"ct":true},"freezedry":{"n":"Freeze-Dry","t":"Ice","c":"S","bp":70,"a":100,"p":0},"freezeshock":{"n":"Freeze Shock","t":"Ice","c":"P","bp":140,"a":90,"p":0},"freezingglare":{"n":"Freezing Glare","t":"Psychic","c":"S","bp":90,"a":100,"p":0},"freezyfrost":{"n":"Freezy Frost","t":"Ice","c":"S","bp":100,"a":90,"p":0},"frenzyplant":{"n":"Frenzy Plant","t":"Grass","c":"S","bp":150,"a":90,"p":0},"frostbreath":{"n":"Frost Breath","t":"Ice","c":"S","bp":60,"a":90,"p":0},"frustration":{"n":"Frustration","t":"Normal","c":"P","bp":0,"a":100,"p":0,"ct":true},"furyattack":{"n":"Fury Attack","t":"Normal","c":"P","bp":15,"a":85,"p":0,"mh":[2,5],"ct":true},"furycutter":{"n":"Fury Cutter","t":"Bug","c":"P","bp":40,"a":95,"p":0,"ct":true},"furyswipes":{"n":"Fury Swipes","t":"Normal","c":"P","bp":18,"a":80,"p":0,"mh":[2,5],"ct":true},"fusionbolt":{"n":"Fusion Bolt","t":"Electric","c":"P","bp":100,"a":100,"p":0},"fusionflare":{"n":"Fusion Flare","t":"Fire","c":"S","bp":100,"a":100,"p":0},"futuresight":{"n":"Future Sight","t":"Psychic","c":"S","bp":120,"a":100,"p":0},"gastroacid":{"n":"Gastro Acid","t":"Poison","c":"T","bp":0,"a":100,"p":0},"geargrind":{"n":"Gear Grind","t":"Steel","c":"P","bp":50,"a":85,"p":0,"mh":2,"ct":true},"gearup":{"n":"Gear Up","t":"Steel","c":"T","bp":0,"a":101,"p":0},"genesissupernova":{"n":"Genesis Supernova","t":"Psychic","c":"S","bp":185,"a":101,"p":0},"geomancy":{"n":"Geomancy","t":"Fairy","c":"T","bp":0,"a":101,"p":0},"gigadrain":{"n":"Giga Drain","t":"Grass","c":"S","bp":75,"a":100,"p":0},"gigaimpact":{"n":"Giga Impact","t":"Normal","c":"P","bp":150,"a":90,"p":0,"ct":true},"gigatonhammer":{"n":"Gigaton Hammer","t":"Steel","c":"P","bp":160,"a":100,"p":0},"gigavolthavoc":{"n":"Gigavolt Havoc","t":"Electric","c":"P","bp":1,"a":101,"p":0},"glaciallance":{"n":"Glacial Lance","t":"Ice","c":"P","bp":120,"a":100,"p":0},"glaciate":{"n":"Glaciate","t":"Ice","c":"S","bp":65,"a":95,"p":0},"glaiverush":{"n":"Glaive Rush","t":"Dragon","c":"P","bp":120,"a":100,"p":0,"ct":true},"glare":{"n":"Glare","t":"Normal","c":"T","bp":0,"a":100,"p":0},"glitzyglow":{"n":"Glitzy Glow","t":"Psychic","c":"S","bp":80,"a":95,"p":0},"gmaxbefuddle":{"n":"G-Max Befuddle","t":"Bug","c":"P","bp":10,"a":101,"p":0},"gmaxcannonade":{"n":"G-Max Cannonade","t":"Water","c":"P","bp":10,"a":101,"p":0},"gmaxcentiferno":{"n":"G-Max Centiferno","t":"Fire","c":"P","bp":10,"a":101,"p":0},"gmaxchistrike":{"n":"G-Max Chi Strike","t":"Fighting","c":"P","bp":10,"a":101,"p":0},"gmaxcuddle":{"n":"G-Max Cuddle","t":"Normal","c":"P","bp":10,"a":101,"p":0},"gmaxdepletion":{"n":"G-Max Depletion","t":"Dragon","c":"P","bp":10,"a":101,"p":0},"gmaxdrumsolo":{"n":"G-Max Drum Solo","t":"Grass","c":"P","bp":160,"a":101,"p":0},"gmaxfinale":{"n":"G-Max Finale","t":"Fairy","c":"P","bp":10,"a":101,"p":0},"gmaxfireball":{"n":"G-Max Fireball","t":"Fire","c":"P","bp":160,"a":101,"p":0},"gmaxfoamburst":{"n":"G-Max Foam Burst","t":"Water","c":"P","bp":10,"a":101,"p":0},"gmaxgoldrush":{"n":"G-Max Gold Rush","t":"Normal","c":"P","bp":10,"a":101,"p":0},"gmaxgravitas":{"n":"G-Max Gravitas","t":"Psychic","c":"P","bp":10,"a":101,"p":0},"gmaxhydrosnipe":{"n":"G-Max Hydrosnipe","t":"Water","c":"P","bp":160,"a":101,"p":0},"gmaxmalodor":{"n":"G-Max Malodor","t":"Poison","c":"P","bp":10,"a":101,"p":0},"gmaxmeltdown":{"n":"G-Max Meltdown","t":"Steel","c":"P","bp":10,"a":101,"p":0},"gmaxoneblow":{"n":"G-Max One Blow","t":"Dark","c":"P","bp":10,"a":101,"p":0},"gmaxrapidflow":{"n":"G-Max Rapid Flow","t":"Water","c":"P","bp":10,"a":101,"p":0},"gmaxreplenish":{"n":"G-Max Replenish","t":"Normal","c":"P","bp":10,"a":101,"p":0},"gmaxresonance":{"n":"G-Max Resonance","t":"Ice","c":"P","bp":10,"a":101,"p":0},"gmaxsandblast":{"n":"G-Max Sandblast","t":"Ground","c":"P","bp":10,"a":101,"p":0},"gmaxsmite":{"n":"G-Max Smite","t":"Fairy","c":"P","bp":10,"a":101,"p":0},"gmaxsnooze":{"n":"G-Max Snooze","t":"Dark","c":"P","bp":10,"a":101,"p":0},"gmaxsteelsurge":{"n":"G-Max Steelsurge","t":"Steel","c":"P","bp":10,"a":101,"p":0},"gmaxstonesurge":{"n":"G-Max Stonesurge","t":"Water","c":"P","bp":10,"a":101,"p":0},"gmaxstunshock":{"n":"G-Max Stun Shock","t":"Electric","c":"P","bp":10,"a":101,"p":0},"gmaxsweetness":{"n":"G-Max Sweetness","t":"Grass","c":"P","bp":10,"a":101,"p":0},"gmaxtartness":{"n":"G-Max Tartness","t":"Grass","c":"P","bp":10,"a":101,"p":0},"gmaxterror":{"n":"G-Max Terror","t":"Ghost","c":"P","bp":10,"a":101,"p":0},"gmaxvinelash":{"n":"G-Max Vine Lash","t":"Grass","c":"P","bp":10,"a":101,"p":0},"gmaxvolcalith":{"n":"G-Max Volcalith","t":"Rock","c":"P","bp":10,"a":101,"p":0},"gmaxvoltcrash":{"n":"G-Max Volt Crash","t":"Electric","c":"P","bp":10,"a":101,"p":0},"gmaxwildfire":{"n":"G-Max Wildfire","t":"Fire","c":"P","bp":10,"a":101,"p":0},"gmaxwindrage":{"n":"G-Max Wind Rage","t":"Flying","c":"P","bp":10,"a":101,"p":0},"grassknot":{"n":"Grass Knot","t":"Grass","c":"S","bp":0,"a":100,"p":0,"ct":true},"grasspledge":{"n":"Grass Pledge","t":"Grass","c":"S","bp":80,"a":100,"p":0},"grasswhistle":{"n":"Grass Whistle","t":"Grass","c":"T","bp":0,"a":55,"p":0},"grassyglide":{"n":"Grassy Glide","t":"Grass","c":"P","bp":55,"a":100,"p":0,"ct":true},"grassyterrain":{"n":"Grassy Terrain","t":"Grass","c":"T","bp":0,"a":101,"p":0},"gravapple":{"n":"Grav Apple","t":"Grass","c":"P","bp":80,"a":100,"p":0},"gravity":{"n":"Gravity","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"growl":{"n":"Growl","t":"Normal","c":"T","bp":0,"a":100,"p":0},"growth":{"n":"Growth","t":"Normal","c":"T","bp":0,"a":101,"p":0},"grudge":{"n":"Grudge","t":"Ghost","c":"T","bp":0,"a":101,"p":0},"guardianofalola":{"n":"Guardian of Alola","t":"Fairy","c":"S","bp":0,"a":101,"p":0},"guardsplit":{"n":"Guard Split","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"guardswap":{"n":"Guard Swap","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"guillotine":{"n":"Guillotine","t":"Normal","c":"P","bp":0,"a":30,"p":0,"ct":true},"gunkshot":{"n":"Gunk Shot","t":"Poison","c":"P","bp":120,"a":80,"p":0},"gust":{"n":"Gust","t":"Flying","c":"S","bp":40,"a":100,"p":0},"gyroball":{"n":"Gyro Ball","t":"Steel","c":"P","bp":0,"a":100,"p":0,"speedbp":"gyroball","ct":true},"hail":{"n":"Hail","t":"Ice","c":"T","bp":0,"a":101,"p":0},"hammerarm":{"n":"Hammer Arm","t":"Fighting","c":"P","bp":100,"a":90,"p":0,"ct":true,"sb":{"spe":-1}},"happyhour":{"n":"Happy Hour","t":"Normal","c":"T","bp":0,"a":101,"p":0},"harden":{"n":"Harden","t":"Normal","c":"T","bp":0,"a":101,"p":0},"hardpress":{"n":"Hard Press","t":"Steel","c":"P","bp":0,"a":100,"p":0,"ct":true},"haze":{"n":"Haze","t":"Ice","c":"T","bp":0,"a":101,"p":0},"headbutt":{"n":"Headbutt","t":"Normal","c":"P","bp":70,"a":100,"p":0,"ct":true},"headcharge":{"n":"Head Charge","t":"Normal","c":"P","bp":120,"a":100,"p":0,"ct":true,"rc":[1,4]},"headlongrush":{"n":"Headlong Rush","t":"Ground","c":"P","bp":120,"a":100,"p":0,"ct":true,"sb":{"def":-1,"spd":-1}},"headsmash":{"n":"Head Smash","t":"Rock","c":"P","bp":150,"a":80,"p":0,"ct":true,"rc":[1,2]},"healbell":{"n":"Heal Bell","t":"Normal","c":"T","bp":0,"a":101,"p":0},"healblock":{"n":"Heal Block","t":"Psychic","c":"T","bp":0,"a":100,"p":0},"healingwish":{"n":"Healing Wish","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"healorder":{"n":"Heal Order","t":"Bug","c":"T","bp":0,"a":101,"p":0},"healpulse":{"n":"Heal Pulse","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"heartstamp":{"n":"Heart Stamp","t":"Psychic","c":"P","bp":60,"a":100,"p":0,"ct":true},"heartswap":{"n":"Heart Swap","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"heatcrash":{"n":"Heat Crash","t":"Fire","c":"P","bp":0,"a":100,"p":0,"ct":true},"heatwave":{"n":"Heat Wave","t":"Fire","c":"S","bp":95,"a":90,"p":0},"heavyslam":{"n":"Heavy Slam","t":"Steel","c":"P","bp":0,"a":100,"p":0,"ct":true},"helpinghand":{"n":"Helping Hand","t":"Normal","c":"T","bp":0,"a":101,"p":5},"hex":{"n":"Hex","t":"Ghost","c":"S","bp":65,"a":100,"p":0},"hiddenpower":{"n":"Hidden Power Water","t":"Water","c":"S","bp":60,"a":100,"p":0},"highhorsepower":{"n":"High Horsepower","t":"Ground","c":"P","bp":95,"a":95,"p":0,"ct":true},"highjumpkick":{"n":"High Jump Kick","t":"Fighting","c":"P","bp":130,"a":90,"p":0,"ct":true},"holdback":{"n":"Hold Back","t":"Normal","c":"P","bp":40,"a":100,"p":0,"ct":true},"holdhands":{"n":"Hold Hands","t":"Normal","c":"T","bp":0,"a":101,"p":0},"honeclaws":{"n":"Hone Claws","t":"Dark","c":"T","bp":0,"a":101,"p":0},"hornattack":{"n":"Horn Attack","t":"Normal","c":"P","bp":65,"a":100,"p":0,"ct":true},"horndrill":{"n":"Horn Drill","t":"Normal","c":"P","bp":0,"a":30,"p":0,"ct":true},"hornleech":{"n":"Horn Leech","t":"Grass","c":"P","bp":75,"a":100,"p":0,"ct":true},"howl":{"n":"Howl","t":"Normal","c":"T","bp":0,"a":101,"p":0},"hurricane":{"n":"Hurricane","t":"Flying","c":"S","bp":110,"a":70,"p":0},"hydrocannon":{"n":"Hydro Cannon","t":"Water","c":"S","bp":150,"a":90,"p":0},"hydropump":{"n":"Hydro Pump","t":"Water","c":"S","bp":110,"a":80,"p":0},"hydrosteam":{"n":"Hydro Steam","t":"Water","c":"S","bp":80,"a":100,"p":0},"hydrovortex":{"n":"Hydro Vortex","t":"Water","c":"P","bp":1,"a":101,"p":0},"hyperbeam":{"n":"Hyper Beam","t":"Normal","c":"S","bp":150,"a":90,"p":0},"hyperdrill":{"n":"Hyper Drill","t":"Normal","c":"P","bp":100,"a":100,"p":0,"ct":true},"hyperfang":{"n":"Hyper Fang","t":"Normal","c":"P","bp":80,"a":90,"p":0,"ct":true},"hyperspacefury":{"n":"Hyperspace Fury","t":"Dark","c":"P","bp":100,"a":101,"p":0,"sb":{"def":-1}},"hyperspacehole":{"n":"Hyperspace Hole","t":"Psychic","c":"S","bp":80,"a":101,"p":0},"hypervoice":{"n":"Hyper Voice","t":"Normal","c":"S","bp":90,"a":100,"p":0},"hypnosis":{"n":"Hypnosis","t":"Psychic","c":"T","bp":0,"a":60,"p":0},"iceball":{"n":"Ice Ball","t":"Ice","c":"P","bp":30,"a":90,"p":0,"ct":true},"icebeam":{"n":"Ice Beam","t":"Ice","c":"S","bp":90,"a":100,"p":0},"iceburn":{"n":"Ice Burn","t":"Ice","c":"S","bp":140,"a":90,"p":0},"icefang":{"n":"Ice Fang","t":"Ice","c":"P","bp":65,"a":95,"p":0,"ct":true},"icehammer":{"n":"Ice Hammer","t":"Ice","c":"P","bp":100,"a":90,"p":0,"ct":true,"sb":{"spe":-1}},"icepunch":{"n":"Ice Punch","t":"Ice","c":"P","bp":75,"a":100,"p":0,"ct":true},"iceshard":{"n":"Ice Shard","t":"Ice","c":"P","bp":40,"a":100,"p":1},"icespinner":{"n":"Ice Spinner","t":"Ice","c":"P","bp":80,"a":100,"p":0,"ct":true},"iciclecrash":{"n":"Icicle Crash","t":"Ice","c":"P","bp":85,"a":90,"p":0},"iciclespear":{"n":"Icicle Spear","t":"Ice","c":"P","bp":25,"a":100,"p":0,"mh":[2,5]},"icywind":{"n":"Icy Wind","t":"Ice","c":"S","bp":55,"a":95,"p":0},"imprison":{"n":"Imprison","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"incinerate":{"n":"Incinerate","t":"Fire","c":"S","bp":60,"a":100,"p":0},"infernalparade":{"n":"Infernal Parade","t":"Ghost","c":"S","bp":60,"a":100,"p":0},"inferno":{"n":"Inferno","t":"Fire","c":"S","bp":100,"a":50,"p":0},"infernooverdrive":{"n":"Inferno Overdrive","t":"Fire","c":"P","bp":1,"a":101,"p":0},"infestation":{"n":"Infestation","t":"Bug","c":"S","bp":20,"a":100,"p":0,"ct":true},"ingrain":{"n":"Ingrain","t":"Grass","c":"T","bp":0,"a":101,"p":0},"instruct":{"n":"Instruct","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"iondeluge":{"n":"Ion Deluge","t":"Electric","c":"T","bp":0,"a":101,"p":1},"irondefense":{"n":"Iron Defense","t":"Steel","c":"T","bp":0,"a":101,"p":0},"ironhead":{"n":"Iron Head","t":"Steel","c":"P","bp":80,"a":100,"p":0,"ct":true},"irontail":{"n":"Iron Tail","t":"Steel","c":"P","bp":100,"a":75,"p":0,"ct":true},"ivycudgel":{"n":"Ivy Cudgel","t":"Grass","c":"P","bp":100,"a":100,"p":0},"jawlock":{"n":"Jaw Lock","t":"Dark","c":"P","bp":80,"a":100,"p":0,"ct":true},"jetpunch":{"n":"Jet Punch","t":"Water","c":"P","bp":60,"a":100,"p":1,"ct":true},"judgment":{"n":"Judgment","t":"Normal","c":"S","bp":100,"a":100,"p":0},"jumpkick":{"n":"Jump Kick","t":"Fighting","c":"P","bp":100,"a":95,"p":0,"ct":true},"junglehealing":{"n":"Jungle Healing","t":"Grass","c":"T","bp":0,"a":101,"p":0},"karatechop":{"n":"Karate Chop","t":"Fighting","c":"P","bp":50,"a":100,"p":0,"ct":true},"kinesis":{"n":"Kinesis","t":"Psychic","c":"T","bp":0,"a":80,"p":0},"kingsshield":{"n":"King's Shield","t":"Steel","c":"T","bp":0,"a":101,"p":4},"knockoff":{"n":"Knock Off","t":"Dark","c":"P","bp":65,"a":100,"p":0,"knock":true,"ct":true},"kowtowcleave":{"n":"Kowtow Cleave","t":"Dark","c":"P","bp":85,"a":101,"p":0,"ct":true},"landswrath":{"n":"Land's Wrath","t":"Ground","c":"P","bp":90,"a":100,"p":0},"laserfocus":{"n":"Laser Focus","t":"Normal","c":"T","bp":0,"a":101,"p":0},"lashout":{"n":"Lash Out","t":"Dark","c":"P","bp":75,"a":100,"p":0,"ct":true},"lastresort":{"n":"Last Resort","t":"Normal","c":"P","bp":140,"a":100,"p":0,"ct":true},"lastrespects":{"n":"Last Respects","t":"Ghost","c":"P","bp":50,"a":100,"p":0},"lavaplume":{"n":"Lava Plume","t":"Fire","c":"S","bp":80,"a":100,"p":0},"leafage":{"n":"Leafage","t":"Grass","c":"P","bp":40,"a":100,"p":0},"leafblade":{"n":"Leaf Blade","t":"Grass","c":"P","bp":90,"a":100,"p":0,"ct":true},"leafstorm":{"n":"Leaf Storm","t":"Grass","c":"S","bp":130,"a":90,"p":0,"sb":{"spa":-2}},"leaftornado":{"n":"Leaf Tornado","t":"Grass","c":"S","bp":65,"a":90,"p":0},"leechlife":{"n":"Leech Life","t":"Bug","c":"P","bp":80,"a":100,"p":0,"ct":true},"leechseed":{"n":"Leech Seed","t":"Grass","c":"T","bp":0,"a":90,"p":0},"leer":{"n":"Leer","t":"Normal","c":"T","bp":0,"a":100,"p":0},"letssnuggleforever":{"n":"Let's Snuggle Forever","t":"Fairy","c":"P","bp":190,"a":101,"p":0,"ct":true},"lick":{"n":"Lick","t":"Ghost","c":"P","bp":30,"a":100,"p":0,"ct":true},"lifedew":{"n":"Life Dew","t":"Water","c":"T","bp":0,"a":101,"p":0},"lightofruin":{"n":"Light of Ruin","t":"Fairy","c":"S","bp":140,"a":90,"p":0,"rc":[1,2]},"lightscreen":{"n":"Light Screen","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"lightthatburnsthesky":{"n":"Light That Burns the Sky","t":"Psychic","c":"S","bp":200,"a":101,"p":0},"liquidation":{"n":"Liquidation","t":"Water","c":"P","bp":85,"a":100,"p":0,"ct":true},"lockon":{"n":"Lock-On","t":"Normal","c":"T","bp":0,"a":101,"p":0},"lovelykiss":{"n":"Lovely Kiss","t":"Normal","c":"T","bp":0,"a":75,"p":0},"lowkick":{"n":"Low Kick","t":"Fighting","c":"P","bp":0,"a":100,"p":0,"ct":true},"lowsweep":{"n":"Low Sweep","t":"Fighting","c":"P","bp":65,"a":100,"p":0,"ct":true},"luckychant":{"n":"Lucky Chant","t":"Normal","c":"T","bp":0,"a":101,"p":0},"luminacrash":{"n":"Lumina Crash","t":"Psychic","c":"S","bp":80,"a":100,"p":0},"lunarblessing":{"n":"Lunar Blessing","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"lunardance":{"n":"Lunar Dance","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"lunge":{"n":"Lunge","t":"Bug","c":"P","bp":80,"a":100,"p":0,"ct":true},"lusterpurge":{"n":"Luster Purge","t":"Psychic","c":"S","bp":95,"a":100,"p":0},"machpunch":{"n":"Mach Punch","t":"Fighting","c":"P","bp":40,"a":100,"p":1,"ct":true},"magicalleaf":{"n":"Magical Leaf","t":"Grass","c":"S","bp":60,"a":101,"p":0},"magicaltorque":{"n":"Magical Torque","t":"Fairy","c":"P","bp":100,"a":100,"p":0},"magiccoat":{"n":"Magic Coat","t":"Psychic","c":"T","bp":0,"a":101,"p":4},"magicpowder":{"n":"Magic Powder","t":"Psychic","c":"T","bp":0,"a":100,"p":0},"magicroom":{"n":"Magic Room","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"magmastorm":{"n":"Magma Storm","t":"Fire","c":"S","bp":100,"a":75,"p":0},"magnetbomb":{"n":"Magnet Bomb","t":"Steel","c":"P","bp":60,"a":101,"p":0},"magneticflux":{"n":"Magnetic Flux","t":"Electric","c":"T","bp":0,"a":101,"p":0},"magnetrise":{"n":"Magnet Rise","t":"Electric","c":"T","bp":0,"a":101,"p":0},"magnitude":{"n":"Magnitude","t":"Ground","c":"P","bp":0,"a":100,"p":0},"makeitrain":{"n":"Make It Rain","t":"Steel","c":"S","bp":120,"a":100,"p":0,"sb":{"spa":-1}},"maliciousmoonsault":{"n":"Malicious Moonsault","t":"Dark","c":"P","bp":180,"a":101,"p":0,"ct":true},"malignantchain":{"n":"Malignant Chain","t":"Poison","c":"S","bp":100,"a":100,"p":0},"matblock":{"n":"Mat Block","t":"Fighting","c":"T","bp":0,"a":101,"p":0},"matchagotcha":{"n":"Matcha Gotcha","t":"Grass","c":"S","bp":80,"a":90,"p":0},"maxairstream":{"n":"Max Airstream","t":"Flying","c":"P","bp":10,"a":101,"p":0},"maxdarkness":{"n":"Max Darkness","t":"Dark","c":"P","bp":10,"a":101,"p":0},"maxflare":{"n":"Max Flare","t":"Fire","c":"P","bp":100,"a":101,"p":0},"maxflutterby":{"n":"Max Flutterby","t":"Bug","c":"P","bp":10,"a":101,"p":0},"maxgeyser":{"n":"Max Geyser","t":"Water","c":"P","bp":10,"a":101,"p":0},"maxguard":{"n":"Max Guard","t":"Normal","c":"T","bp":0,"a":101,"p":4},"maxhailstorm":{"n":"Max Hailstorm","t":"Ice","c":"P","bp":10,"a":101,"p":0},"maxknuckle":{"n":"Max Knuckle","t":"Fighting","c":"P","bp":10,"a":101,"p":0},"maxlightning":{"n":"Max Lightning","t":"Electric","c":"P","bp":10,"a":101,"p":0},"maxmindstorm":{"n":"Max Mindstorm","t":"Psychic","c":"P","bp":10,"a":101,"p":0},"maxooze":{"n":"Max Ooze","t":"Poison","c":"P","bp":10,"a":101,"p":0},"maxovergrowth":{"n":"Max Overgrowth","t":"Grass","c":"P","bp":10,"a":101,"p":0},"maxphantasm":{"n":"Max Phantasm","t":"Ghost","c":"P","bp":10,"a":101,"p":0},"maxquake":{"n":"Max Quake","t":"Ground","c":"P","bp":10,"a":101,"p":0},"maxrockfall":{"n":"Max Rockfall","t":"Rock","c":"P","bp":10,"a":101,"p":0},"maxstarfall":{"n":"Max Starfall","t":"Fairy","c":"P","bp":10,"a":101,"p":0},"maxsteelspike":{"n":"Max Steelspike","t":"Steel","c":"P","bp":10,"a":101,"p":0},"maxstrike":{"n":"Max Strike","t":"Normal","c":"P","bp":10,"a":101,"p":0},"maxwyrmwind":{"n":"Max Wyrmwind","t":"Dragon","c":"P","bp":10,"a":101,"p":0},"meanlook":{"n":"Mean Look","t":"Normal","c":"T","bp":0,"a":101,"p":0},"meditate":{"n":"Meditate","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"mefirst":{"n":"Me First","t":"Normal","c":"T","bp":0,"a":101,"p":0},"megadrain":{"n":"Mega Drain","t":"Grass","c":"S","bp":40,"a":100,"p":0},"megahorn":{"n":"Megahorn","t":"Bug","c":"P","bp":120,"a":85,"p":0,"ct":true},"megakick":{"n":"Mega Kick","t":"Normal","c":"P","bp":120,"a":75,"p":0,"ct":true},"megapunch":{"n":"Mega Punch","t":"Normal","c":"P","bp":80,"a":85,"p":0,"ct":true},"memento":{"n":"Memento","t":"Dark","c":"T","bp":0,"a":100,"p":0},"menacingmoonrazemaelstrom":{"n":"Menacing Moonraze Maelstrom","t":"Ghost","c":"S","bp":200,"a":101,"p":0},"metalburst":{"n":"Metal Burst","t":"Steel","c":"P","bp":0,"a":100,"p":0},"metalclaw":{"n":"Metal Claw","t":"Steel","c":"P","bp":50,"a":95,"p":0,"ct":true},"metalsound":{"n":"Metal Sound","t":"Steel","c":"T","bp":0,"a":85,"p":0},"meteorassault":{"n":"Meteor Assault","t":"Fighting","c":"P","bp":150,"a":100,"p":0},"meteorbeam":{"n":"Meteor Beam","t":"Rock","c":"S","bp":120,"a":90,"p":0},"meteormash":{"n":"Meteor Mash","t":"Steel","c":"P","bp":90,"a":90,"p":0,"ct":true},"metronome":{"n":"Metronome","t":"Normal","c":"T","bp":0,"a":101,"p":0},"mightycleave":{"n":"Mighty Cleave","t":"Rock","c":"P","bp":95,"a":100,"p":0,"ct":true},"milkdrink":{"n":"Milk Drink","t":"Normal","c":"T","bp":0,"a":101,"p":0},"mimic":{"n":"Mimic","t":"Normal","c":"T","bp":0,"a":101,"p":0},"mindblown":{"n":"Mind Blown","t":"Fire","c":"S","bp":150,"a":100,"p":0},"mindreader":{"n":"Mind Reader","t":"Normal","c":"T","bp":0,"a":101,"p":0},"minimize":{"n":"Minimize","t":"Normal","c":"T","bp":0,"a":101,"p":0},"miracleeye":{"n":"Miracle Eye","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"mirrorcoat":{"n":"Mirror Coat","t":"Psychic","c":"S","bp":0,"a":100,"p":-5},"mirrormove":{"n":"Mirror Move","t":"Flying","c":"T","bp":0,"a":101,"p":0},"mirrorshot":{"n":"Mirror Shot","t":"Steel","c":"S","bp":65,"a":85,"p":0},"mist":{"n":"Mist","t":"Ice","c":"T","bp":0,"a":101,"p":0},"mistball":{"n":"Mist Ball","t":"Psychic","c":"S","bp":95,"a":100,"p":0},"mistyexplosion":{"n":"Misty Explosion","t":"Fairy","c":"S","bp":100,"a":100,"p":0},"mistyterrain":{"n":"Misty Terrain","t":"Fairy","c":"T","bp":0,"a":101,"p":0},"moonblast":{"n":"Moonblast","t":"Fairy","c":"S","bp":95,"a":100,"p":0},"moongeistbeam":{"n":"Moongeist Beam","t":"Ghost","c":"S","bp":100,"a":100,"p":0},"moonlight":{"n":"Moonlight","t":"Fairy","c":"T","bp":0,"a":101,"p":0},"morningsun":{"n":"Morning Sun","t":"Normal","c":"T","bp":0,"a":101,"p":0},"mortalspin":{"n":"Mortal Spin","t":"Poison","c":"P","bp":30,"a":100,"p":0,"ct":true},"mountaingale":{"n":"Mountain Gale","t":"Ice","c":"P","bp":100,"a":85,"p":0},"mudbomb":{"n":"Mud Bomb","t":"Ground","c":"S","bp":65,"a":85,"p":0},"muddywater":{"n":"Muddy Water","t":"Water","c":"S","bp":90,"a":85,"p":0},"mudshot":{"n":"Mud Shot","t":"Ground","c":"S","bp":55,"a":95,"p":0},"mudslap":{"n":"Mud-Slap","t":"Ground","c":"S","bp":20,"a":100,"p":0},"mudsport":{"n":"Mud Sport","t":"Ground","c":"T","bp":0,"a":101,"p":0},"multiattack":{"n":"Multi-Attack","t":"Normal","c":"P","bp":120,"a":100,"p":0,"ct":true},"mysticalfire":{"n":"Mystical Fire","t":"Fire","c":"S","bp":75,"a":100,"p":0},"mysticalpower":{"n":"Mystical Power","t":"Psychic","c":"S","bp":70,"a":90,"p":0},"nastyplot":{"n":"Nasty Plot","t":"Dark","c":"T","bp":0,"a":101,"p":0},"naturalgift":{"n":"Natural Gift","t":"Normal","c":"P","bp":0,"a":100,"p":0},"naturepower":{"n":"Nature Power","t":"Normal","c":"T","bp":0,"a":101,"p":0},"naturesmadness":{"n":"Nature's Madness","t":"Fairy","c":"S","bp":0,"a":90,"p":0},"needlearm":{"n":"Needle Arm","t":"Grass","c":"P","bp":60,"a":100,"p":0,"ct":true},"neverendingnightmare":{"n":"Never-Ending Nightmare","t":"Ghost","c":"P","bp":1,"a":101,"p":0},"nightdaze":{"n":"Night Daze","t":"Dark","c":"S","bp":85,"a":95,"p":0},"nightmare":{"n":"Nightmare","t":"Ghost","c":"T","bp":0,"a":100,"p":0},"nightshade":{"n":"Night Shade","t":"Ghost","c":"S","bp":0,"a":100,"p":0},"nightslash":{"n":"Night Slash","t":"Dark","c":"P","bp":70,"a":100,"p":0,"ct":true},"nihillight":{"n":"Nihil Light","t":"Dragon","c":"S","bp":100,"a":100,"p":0},"nobleroar":{"n":"Noble Roar","t":"Normal","c":"T","bp":0,"a":100,"p":0},"noretreat":{"n":"No Retreat","t":"Fighting","c":"T","bp":0,"a":101,"p":0},"noxioustorque":{"n":"Noxious Torque","t":"Poison","c":"P","bp":100,"a":100,"p":0},"nuzzle":{"n":"Nuzzle","t":"Electric","c":"P","bp":20,"a":100,"p":0,"ct":true},"oblivionwing":{"n":"Oblivion Wing","t":"Flying","c":"S","bp":80,"a":100,"p":0},"obstruct":{"n":"Obstruct","t":"Dark","c":"T","bp":0,"a":100,"p":4},"oceanicoperetta":{"n":"Oceanic Operetta","t":"Water","c":"S","bp":195,"a":101,"p":0},"octazooka":{"n":"Octazooka","t":"Water","c":"S","bp":65,"a":85,"p":0},"octolock":{"n":"Octolock","t":"Fighting","c":"T","bp":0,"a":100,"p":0},"odorsleuth":{"n":"Odor Sleuth","t":"Normal","c":"T","bp":0,"a":101,"p":0},"ominouswind":{"n":"Ominous Wind","t":"Ghost","c":"S","bp":60,"a":100,"p":0},"orderup":{"n":"Order Up","t":"Dragon","c":"P","bp":80,"a":100,"p":0},"originpulse":{"n":"Origin Pulse","t":"Water","c":"S","bp":110,"a":85,"p":0},"outrage":{"n":"Outrage","t":"Dragon","c":"P","bp":120,"a":100,"p":0,"ct":true},"overdrive":{"n":"Overdrive","t":"Electric","c":"S","bp":80,"a":100,"p":0},"overheat":{"n":"Overheat","t":"Fire","c":"S","bp":130,"a":90,"p":0,"sb":{"spa":-2}},"painsplit":{"n":"Pain Split","t":"Normal","c":"T","bp":0,"a":101,"p":0},"paraboliccharge":{"n":"Parabolic Charge","t":"Electric","c":"S","bp":65,"a":100,"p":0},"partingshot":{"n":"Parting Shot","t":"Dark","c":"T","bp":0,"a":100,"p":0},"payback":{"n":"Payback","t":"Dark","c":"P","bp":50,"a":100,"p":0,"ct":true},"payday":{"n":"Pay Day","t":"Normal","c":"P","bp":40,"a":100,"p":0},"peck":{"n":"Peck","t":"Flying","c":"P","bp":35,"a":100,"p":0,"ct":true},"perishsong":{"n":"Perish Song","t":"Normal","c":"T","bp":0,"a":101,"p":0},"petalblizzard":{"n":"Petal Blizzard","t":"Grass","c":"P","bp":90,"a":100,"p":0},"petaldance":{"n":"Petal Dance","t":"Grass","c":"S","bp":120,"a":100,"p":0,"ct":true},"phantomforce":{"n":"Phantom Force","t":"Ghost","c":"P","bp":90,"a":100,"p":0,"ct":true},"photongeyser":{"n":"Photon Geyser","t":"Psychic","c":"S","bp":100,"a":100,"p":0},"pikapapow":{"n":"Pika Papow","t":"Electric","c":"S","bp":0,"a":101,"p":0},"pinmissile":{"n":"Pin Missile","t":"Bug","c":"P","bp":25,"a":95,"p":0,"mh":[2,5]},"plasmafists":{"n":"Plasma Fists","t":"Electric","c":"P","bp":100,"a":100,"p":0,"ct":true},"playnice":{"n":"Play Nice","t":"Normal","c":"T","bp":0,"a":101,"p":0},"playrough":{"n":"Play Rough","t":"Fairy","c":"P","bp":90,"a":90,"p":0,"ct":true},"pluck":{"n":"Pluck","t":"Flying","c":"P","bp":60,"a":100,"p":0,"ct":true},"poisonfang":{"n":"Poison Fang","t":"Poison","c":"P","bp":50,"a":100,"p":0,"ct":true},"poisongas":{"n":"Poison Gas","t":"Poison","c":"T","bp":0,"a":90,"p":0},"poisonjab":{"n":"Poison Jab","t":"Poison","c":"P","bp":80,"a":100,"p":0,"ct":true},"poisonpowder":{"n":"Poison Powder","t":"Poison","c":"T","bp":0,"a":75,"p":0},"poisonsting":{"n":"Poison Sting","t":"Poison","c":"P","bp":15,"a":100,"p":0},"poisontail":{"n":"Poison Tail","t":"Poison","c":"P","bp":50,"a":100,"p":0,"ct":true},"pollenpuff":{"n":"Pollen Puff","t":"Bug","c":"S","bp":90,"a":100,"p":0},"poltergeist":{"n":"Poltergeist","t":"Ghost","c":"P","bp":110,"a":90,"p":0},"populationbomb":{"n":"Population Bomb","t":"Normal","c":"P","bp":20,"a":90,"p":0,"mh":10,"ct":true},"pounce":{"n":"Pounce","t":"Bug","c":"P","bp":50,"a":100,"p":0,"ct":true},"pound":{"n":"Pound","t":"Normal","c":"P","bp":40,"a":100,"p":0,"ct":true},"powder":{"n":"Powder","t":"Bug","c":"T","bp":0,"a":100,"p":1},"powdersnow":{"n":"Powder Snow","t":"Ice","c":"S","bp":40,"a":100,"p":0},"powergem":{"n":"Power Gem","t":"Rock","c":"S","bp":80,"a":100,"p":0},"powershift":{"n":"Power Shift","t":"Normal","c":"T","bp":0,"a":101,"p":0},"powersplit":{"n":"Power Split","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"powerswap":{"n":"Power Swap","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"powertrick":{"n":"Power Trick","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"powertrip":{"n":"Power Trip","t":"Dark","c":"P","bp":20,"a":100,"p":0,"ct":true},"poweruppunch":{"n":"Power-Up Punch","t":"Fighting","c":"P","bp":40,"a":100,"p":0,"ct":true},"powerwhip":{"n":"Power Whip","t":"Grass","c":"P","bp":120,"a":85,"p":0,"ct":true},"precipiceblades":{"n":"Precipice Blades","t":"Ground","c":"P","bp":120,"a":85,"p":0},"present":{"n":"Present","t":"Normal","c":"P","bp":0,"a":90,"p":0},"prismaticlaser":{"n":"Prismatic Laser","t":"Psychic","c":"S","bp":160,"a":100,"p":0},"protect":{"n":"Protect","t":"Normal","c":"T","bp":0,"a":101,"p":4},"psybeam":{"n":"Psybeam","t":"Psychic","c":"S","bp":65,"a":100,"p":0},"psyblade":{"n":"Psyblade","t":"Psychic","c":"P","bp":80,"a":100,"p":0,"ct":true},"psychic":{"n":"Psychic","t":"Psychic","c":"S","bp":90,"a":100,"p":0},"psychicfangs":{"n":"Psychic Fangs","t":"Psychic","c":"P","bp":85,"a":100,"p":0,"ct":true},"psychicnoise":{"n":"Psychic Noise","t":"Psychic","c":"S","bp":75,"a":100,"p":0},"psychicterrain":{"n":"Psychic Terrain","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"psychoboost":{"n":"Psycho Boost","t":"Psychic","c":"S","bp":140,"a":90,"p":0,"sb":{"spa":-2}},"psychocut":{"n":"Psycho Cut","t":"Psychic","c":"P","bp":70,"a":100,"p":0},"psychoshift":{"n":"Psycho Shift","t":"Psychic","c":"T","bp":0,"a":100,"p":0},"psychup":{"n":"Psych Up","t":"Normal","c":"T","bp":0,"a":101,"p":0},"psyshieldbash":{"n":"Psyshield Bash","t":"Psychic","c":"P","bp":70,"a":90,"p":0,"ct":true},"psyshock":{"n":"Psyshock","t":"Psychic","c":"S","bp":80,"a":100,"p":0},"psystrike":{"n":"Psystrike","t":"Psychic","c":"S","bp":100,"a":100,"p":0},"psywave":{"n":"Psywave","t":"Psychic","c":"S","bp":0,"a":100,"p":0},"pulverizingpancake":{"n":"Pulverizing Pancake","t":"Normal","c":"P","bp":210,"a":101,"p":0,"ct":true},"punishment":{"n":"Punishment","t":"Dark","c":"P","bp":0,"a":100,"p":0,"ct":true},"purify":{"n":"Purify","t":"Poison","c":"T","bp":0,"a":101,"p":0},"pursuit":{"n":"Pursuit","t":"Dark","c":"P","bp":40,"a":100,"p":0,"ct":true},"pyroball":{"n":"Pyro Ball","t":"Fire","c":"P","bp":120,"a":90,"p":0},"quash":{"n":"Quash","t":"Dark","c":"T","bp":0,"a":100,"p":0},"quickattack":{"n":"Quick Attack","t":"Normal","c":"P","bp":40,"a":100,"p":1,"ct":true},"quickguard":{"n":"Quick Guard","t":"Fighting","c":"T","bp":0,"a":101,"p":3},"quiverdance":{"n":"Quiver Dance","t":"Bug","c":"T","bp":0,"a":101,"p":0},"rage":{"n":"Rage","t":"Normal","c":"P","bp":20,"a":100,"p":0,"ct":true},"ragefist":{"n":"Rage Fist","t":"Ghost","c":"P","bp":50,"a":100,"p":0,"ct":true},"ragepowder":{"n":"Rage Powder","t":"Bug","c":"T","bp":0,"a":101,"p":2},"ragingbull":{"n":"Raging Bull","t":"Normal","c":"P","bp":90,"a":100,"p":0,"ct":true},"ragingfury":{"n":"Raging Fury","t":"Fire","c":"P","bp":120,"a":100,"p":0},"raindance":{"n":"Rain Dance","t":"Water","c":"T","bp":0,"a":101,"p":0},"rapidspin":{"n":"Rapid Spin","t":"Normal","c":"P","bp":50,"a":100,"p":0,"ct":true},"razorleaf":{"n":"Razor Leaf","t":"Grass","c":"P","bp":55,"a":95,"p":0},"razorshell":{"n":"Razor Shell","t":"Water","c":"P","bp":75,"a":95,"p":0,"ct":true},"razorwind":{"n":"Razor Wind","t":"Normal","c":"S","bp":80,"a":100,"p":0},"recover":{"n":"Recover","t":"Normal","c":"T","bp":0,"a":101,"p":0},"recycle":{"n":"Recycle","t":"Normal","c":"T","bp":0,"a":101,"p":0},"reflect":{"n":"Reflect","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"reflecttype":{"n":"Reflect Type","t":"Normal","c":"T","bp":0,"a":101,"p":0},"refresh":{"n":"Refresh","t":"Normal","c":"T","bp":0,"a":101,"p":0},"relicsong":{"n":"Relic Song","t":"Normal","c":"S","bp":75,"a":100,"p":0},"rest":{"n":"Rest","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"retaliate":{"n":"Retaliate","t":"Normal","c":"P","bp":70,"a":100,"p":0,"ct":true},"return":{"n":"Return","t":"Normal","c":"P","bp":0,"a":100,"p":0,"ct":true},"revelationdance":{"n":"Revelation Dance","t":"Normal","c":"S","bp":90,"a":100,"p":0},"revenge":{"n":"Revenge","t":"Fighting","c":"P","bp":60,"a":100,"p":-4,"ct":true},"reversal":{"n":"Reversal","t":"Fighting","c":"P","bp":0,"a":100,"p":0,"ct":true},"revivalblessing":{"n":"Revival Blessing","t":"Normal","c":"T","bp":0,"a":101,"p":0},"risingvoltage":{"n":"Rising Voltage","t":"Electric","c":"S","bp":70,"a":100,"p":0},"roar":{"n":"Roar","t":"Normal","c":"T","bp":0,"a":101,"p":-6},"roaroftime":{"n":"Roar of Time","t":"Dragon","c":"S","bp":150,"a":90,"p":0},"rockblast":{"n":"Rock Blast","t":"Rock","c":"P","bp":25,"a":90,"p":0,"mh":[2,5]},"rockclimb":{"n":"Rock Climb","t":"Normal","c":"P","bp":90,"a":85,"p":0,"ct":true},"rockpolish":{"n":"Rock Polish","t":"Rock","c":"T","bp":0,"a":101,"p":0},"rockslide":{"n":"Rock Slide","t":"Rock","c":"P","bp":75,"a":90,"p":0},"rocksmash":{"n":"Rock Smash","t":"Fighting","c":"P","bp":40,"a":100,"p":0,"ct":true},"rockthrow":{"n":"Rock Throw","t":"Rock","c":"P","bp":50,"a":90,"p":0},"rocktomb":{"n":"Rock Tomb","t":"Rock","c":"P","bp":60,"a":95,"p":0},"rockwrecker":{"n":"Rock Wrecker","t":"Rock","c":"P","bp":150,"a":90,"p":0},"roleplay":{"n":"Role Play","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"rollingkick":{"n":"Rolling Kick","t":"Fighting","c":"P","bp":60,"a":85,"p":0,"ct":true},"rollout":{"n":"Rollout","t":"Rock","c":"P","bp":30,"a":90,"p":0,"ct":true},"roost":{"n":"Roost","t":"Flying","c":"T","bp":0,"a":101,"p":0},"rototiller":{"n":"Rototiller","t":"Ground","c":"T","bp":0,"a":101,"p":0},"round":{"n":"Round","t":"Normal","c":"S","bp":60,"a":100,"p":0},"ruination":{"n":"Ruination","t":"Dark","c":"S","bp":0,"a":90,"p":0},"sacredfire":{"n":"Sacred Fire","t":"Fire","c":"P","bp":100,"a":95,"p":0},"sacredsword":{"n":"Sacred Sword","t":"Fighting","c":"P","bp":90,"a":100,"p":0,"ct":true},"safeguard":{"n":"Safeguard","t":"Normal","c":"T","bp":0,"a":101,"p":0},"saltcure":{"n":"Salt Cure","t":"Rock","c":"P","bp":40,"a":100,"p":0},"sandattack":{"n":"Sand Attack","t":"Ground","c":"T","bp":0,"a":100,"p":0},"sandsearstorm":{"n":"Sandsear Storm","t":"Ground","c":"S","bp":100,"a":80,"p":0},"sandstorm":{"n":"Sandstorm","t":"Rock","c":"T","bp":0,"a":101,"p":0},"sandtomb":{"n":"Sand Tomb","t":"Ground","c":"P","bp":35,"a":85,"p":0},"sappyseed":{"n":"Sappy Seed","t":"Grass","c":"P","bp":100,"a":90,"p":0},"savagespinout":{"n":"Savage Spin-Out","t":"Bug","c":"P","bp":1,"a":101,"p":0},"scald":{"n":"Scald","t":"Water","c":"S","bp":80,"a":100,"p":0},"scaleshot":{"n":"Scale Shot","t":"Dragon","c":"P","bp":25,"a":90,"p":0,"mh":[2,5]},"scaryface":{"n":"Scary Face","t":"Normal","c":"T","bp":0,"a":100,"p":0},"scorchingsands":{"n":"Scorching Sands","t":"Ground","c":"S","bp":70,"a":100,"p":0},"scratch":{"n":"Scratch","t":"Normal","c":"P","bp":40,"a":100,"p":0,"ct":true},"screech":{"n":"Screech","t":"Normal","c":"T","bp":0,"a":85,"p":0},"searingshot":{"n":"Searing Shot","t":"Fire","c":"S","bp":100,"a":100,"p":0},"searingsunrazesmash":{"n":"Searing Sunraze Smash","t":"Steel","c":"P","bp":200,"a":101,"p":0,"ct":true},"secretpower":{"n":"Secret Power","t":"Normal","c":"P","bp":70,"a":100,"p":0},"secretsword":{"n":"Secret Sword","t":"Fighting","c":"S","bp":85,"a":100,"p":0},"seedbomb":{"n":"Seed Bomb","t":"Grass","c":"P","bp":80,"a":100,"p":0},"seedflare":{"n":"Seed Flare","t":"Grass","c":"S","bp":120,"a":85,"p":0},"seismictoss":{"n":"Seismic Toss","t":"Fighting","c":"P","bp":0,"a":100,"p":0,"ct":true},"selfdestruct":{"n":"Self-Destruct","t":"Normal","c":"P","bp":200,"a":100,"p":0},"shadowball":{"n":"Shadow Ball","t":"Ghost","c":"S","bp":80,"a":100,"p":0},"shadowbone":{"n":"Shadow Bone","t":"Ghost","c":"P","bp":85,"a":100,"p":0},"shadowclaw":{"n":"Shadow Claw","t":"Ghost","c":"P","bp":70,"a":100,"p":0,"ct":true},"shadowforce":{"n":"Shadow Force","t":"Ghost","c":"P","bp":120,"a":100,"p":0,"ct":true},"shadowpunch":{"n":"Shadow Punch","t":"Ghost","c":"P","bp":60,"a":101,"p":0,"ct":true},"shadowsneak":{"n":"Shadow Sneak","t":"Ghost","c":"P","bp":40,"a":100,"p":1,"ct":true},"sharpen":{"n":"Sharpen","t":"Normal","c":"T","bp":0,"a":101,"p":0},"shatteredpsyche":{"n":"Shattered Psyche","t":"Psychic","c":"P","bp":1,"a":101,"p":0},"shedtail":{"n":"Shed Tail","t":"Normal","c":"T","bp":0,"a":101,"p":0},"sheercold":{"n":"Sheer Cold","t":"Ice","c":"S","bp":0,"a":30,"p":0},"shellsidearm":{"n":"Shell Side Arm","t":"Poison","c":"S","bp":90,"a":100,"p":0},"shellsmash":{"n":"Shell Smash","t":"Normal","c":"T","bp":0,"a":101,"p":0},"shelltrap":{"n":"Shell Trap","t":"Fire","c":"S","bp":150,"a":100,"p":-3},"shelter":{"n":"Shelter","t":"Steel","c":"T","bp":0,"a":101,"p":0},"shiftgear":{"n":"Shift Gear","t":"Steel","c":"T","bp":0,"a":101,"p":0},"shockwave":{"n":"Shock Wave","t":"Electric","c":"S","bp":60,"a":101,"p":0},"shoreup":{"n":"Shore Up","t":"Ground","c":"T","bp":0,"a":101,"p":0},"signalbeam":{"n":"Signal Beam","t":"Bug","c":"S","bp":75,"a":100,"p":0},"silktrap":{"n":"Silk Trap","t":"Bug","c":"T","bp":0,"a":101,"p":4},"silverwind":{"n":"Silver Wind","t":"Bug","c":"S","bp":60,"a":100,"p":0},"simplebeam":{"n":"Simple Beam","t":"Normal","c":"T","bp":0,"a":100,"p":0},"sing":{"n":"Sing","t":"Normal","c":"T","bp":0,"a":55,"p":0},"sinisterarrowraid":{"n":"Sinister Arrow Raid","t":"Ghost","c":"P","bp":180,"a":101,"p":0},"sizzlyslide":{"n":"Sizzly Slide","t":"Fire","c":"P","bp":60,"a":100,"p":0,"ct":true},"sketch":{"n":"Sketch","t":"Normal","c":"T","bp":0,"a":101,"p":0},"skillswap":{"n":"Skill Swap","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"skittersmack":{"n":"Skitter Smack","t":"Bug","c":"P","bp":70,"a":90,"p":0,"ct":true},"skullbash":{"n":"Skull Bash","t":"Normal","c":"P","bp":130,"a":100,"p":0,"ct":true},"skyattack":{"n":"Sky Attack","t":"Flying","c":"P","bp":140,"a":90,"p":0},"skydrop":{"n":"Sky Drop","t":"Flying","c":"P","bp":60,"a":100,"p":0,"ct":true},"skyuppercut":{"n":"Sky Uppercut","t":"Fighting","c":"P","bp":85,"a":90,"p":0,"ct":true},"slackoff":{"n":"Slack Off","t":"Normal","c":"T","bp":0,"a":101,"p":0},"slam":{"n":"Slam","t":"Normal","c":"P","bp":80,"a":75,"p":0,"ct":true},"slash":{"n":"Slash","t":"Normal","c":"P","bp":70,"a":100,"p":0,"ct":true},"sleeppowder":{"n":"Sleep Powder","t":"Grass","c":"T","bp":0,"a":75,"p":0},"sleeptalk":{"n":"Sleep Talk","t":"Normal","c":"T","bp":0,"a":101,"p":0},"sludge":{"n":"Sludge","t":"Poison","c":"S","bp":65,"a":100,"p":0},"sludgebomb":{"n":"Sludge Bomb","t":"Poison","c":"S","bp":90,"a":100,"p":0},"sludgewave":{"n":"Sludge Wave","t":"Poison","c":"S","bp":95,"a":100,"p":0},"smackdown":{"n":"Smack Down","t":"Rock","c":"P","bp":50,"a":100,"p":0},"smartstrike":{"n":"Smart Strike","t":"Steel","c":"P","bp":70,"a":101,"p":0,"ct":true},"smellingsalts":{"n":"Smelling Salts","t":"Normal","c":"P","bp":70,"a":100,"p":0,"ct":true},"smog":{"n":"Smog","t":"Poison","c":"S","bp":30,"a":70,"p":0},"smokescreen":{"n":"Smokescreen","t":"Normal","c":"T","bp":0,"a":100,"p":0},"snaptrap":{"n":"Snap Trap","t":"Grass","c":"P","bp":35,"a":100,"p":0,"ct":true},"snarl":{"n":"Snarl","t":"Dark","c":"S","bp":55,"a":95,"p":0},"snatch":{"n":"Snatch","t":"Dark","c":"T","bp":0,"a":101,"p":4},"snipeshot":{"n":"Snipe Shot","t":"Water","c":"S","bp":80,"a":100,"p":0},"snore":{"n":"Snore","t":"Normal","c":"S","bp":50,"a":100,"p":0},"snowscape":{"n":"Snowscape","t":"Ice","c":"T","bp":0,"a":101,"p":0},"soak":{"n":"Soak","t":"Water","c":"T","bp":0,"a":100,"p":0},"softboiled":{"n":"Soft-Boiled","t":"Normal","c":"T","bp":0,"a":101,"p":0},"solarbeam":{"n":"Solar Beam","t":"Grass","c":"S","bp":120,"a":100,"p":0},"solarblade":{"n":"Solar Blade","t":"Grass","c":"P","bp":125,"a":100,"p":0,"ct":true},"sonicboom":{"n":"Sonic Boom","t":"Normal","c":"S","bp":0,"a":90,"p":0},"soulstealing7starstrike":{"n":"Soul-Stealing 7-Star Strike","t":"Ghost","c":"P","bp":195,"a":101,"p":0,"ct":true},"spacialrend":{"n":"Spacial Rend","t":"Dragon","c":"S","bp":100,"a":95,"p":0},"spark":{"n":"Spark","t":"Electric","c":"P","bp":65,"a":100,"p":0,"ct":true},"sparklingaria":{"n":"Sparkling Aria","t":"Water","c":"S","bp":90,"a":100,"p":0},"sparklyswirl":{"n":"Sparkly Swirl","t":"Fairy","c":"S","bp":120,"a":85,"p":0},"spectralthief":{"n":"Spectral Thief","t":"Ghost","c":"P","bp":90,"a":100,"p":0,"ct":true},"speedswap":{"n":"Speed Swap","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"spicyextract":{"n":"Spicy Extract","t":"Grass","c":"T","bp":0,"a":101,"p":0},"spiderweb":{"n":"Spider Web","t":"Bug","c":"T","bp":0,"a":101,"p":0},"spikecannon":{"n":"Spike Cannon","t":"Normal","c":"P","bp":20,"a":100,"p":0,"mh":[2,5]},"spikes":{"n":"Spikes","t":"Ground","c":"T","bp":0,"a":101,"p":0},"spikyshield":{"n":"Spiky Shield","t":"Grass","c":"T","bp":0,"a":101,"p":4},"spinout":{"n":"Spin Out","t":"Steel","c":"P","bp":100,"a":100,"p":0,"ct":true,"sb":{"spe":-2}},"spiritbreak":{"n":"Spirit Break","t":"Fairy","c":"P","bp":75,"a":100,"p":0,"ct":true},"spiritshackle":{"n":"Spirit Shackle","t":"Ghost","c":"P","bp":80,"a":100,"p":0},"spite":{"n":"Spite","t":"Ghost","c":"T","bp":0,"a":100,"p":0},"spitup":{"n":"Spit Up","t":"Normal","c":"S","bp":0,"a":100,"p":0},"splash":{"n":"Splash","t":"Normal","c":"T","bp":0,"a":101,"p":0},"splinteredstormshards":{"n":"Splintered Stormshards","t":"Rock","c":"P","bp":190,"a":101,"p":0},"splishysplash":{"n":"Splishy Splash","t":"Water","c":"S","bp":90,"a":100,"p":0},"spore":{"n":"Spore","t":"Grass","c":"T","bp":0,"a":100,"p":0},"spotlight":{"n":"Spotlight","t":"Normal","c":"T","bp":0,"a":101,"p":3},"springtidestorm":{"n":"Springtide Storm","t":"Fairy","c":"S","bp":100,"a":80,"p":0},"stealthrock":{"n":"Stealth Rock","t":"Rock","c":"T","bp":0,"a":101,"p":0},"steameruption":{"n":"Steam Eruption","t":"Water","c":"S","bp":110,"a":95,"p":0},"steamroller":{"n":"Steamroller","t":"Bug","c":"P","bp":65,"a":100,"p":0,"ct":true},"steelbeam":{"n":"Steel Beam","t":"Steel","c":"S","bp":140,"a":95,"p":0},"steelroller":{"n":"Steel Roller","t":"Steel","c":"P","bp":130,"a":100,"p":0,"ct":true},"steelwing":{"n":"Steel Wing","t":"Steel","c":"P","bp":70,"a":90,"p":0,"ct":true},"stickyweb":{"n":"Sticky Web","t":"Bug","c":"T","bp":0,"a":101,"p":0},"stockpile":{"n":"Stockpile","t":"Normal","c":"T","bp":0,"a":101,"p":0},"stokedsparksurfer":{"n":"Stoked Sparksurfer","t":"Electric","c":"S","bp":175,"a":101,"p":0},"stomp":{"n":"Stomp","t":"Normal","c":"P","bp":65,"a":100,"p":0,"ct":true},"stompingtantrum":{"n":"Stomping Tantrum","t":"Ground","c":"P","bp":75,"a":100,"p":0,"ct":true},"stoneaxe":{"n":"Stone Axe","t":"Rock","c":"P","bp":65,"a":90,"p":0,"ct":true},"stoneedge":{"n":"Stone Edge","t":"Rock","c":"P","bp":100,"a":80,"p":0},"storedpower":{"n":"Stored Power","t":"Psychic","c":"S","bp":20,"a":100,"p":0},"stormthrow":{"n":"Storm Throw","t":"Fighting","c":"P","bp":60,"a":100,"p":0,"ct":true},"strangesteam":{"n":"Strange Steam","t":"Fairy","c":"S","bp":90,"a":95,"p":0},"strength":{"n":"Strength","t":"Normal","c":"P","bp":80,"a":100,"p":0,"ct":true},"strengthsap":{"n":"Strength Sap","t":"Grass","c":"T","bp":0,"a":100,"p":0},"stringshot":{"n":"String Shot","t":"Bug","c":"T","bp":0,"a":95,"p":0},"struggle":{"n":"Struggle","t":"Normal","c":"P","bp":50,"a":101,"p":0,"ct":true},"strugglebug":{"n":"Struggle Bug","t":"Bug","c":"S","bp":50,"a":100,"p":0},"stuffcheeks":{"n":"Stuff Cheeks","t":"Normal","c":"T","bp":0,"a":101,"p":0},"stunspore":{"n":"Stun Spore","t":"Grass","c":"T","bp":0,"a":75,"p":0},"submission":{"n":"Submission","t":"Fighting","c":"P","bp":80,"a":80,"p":0,"ct":true,"rc":[1,4]},"substitute":{"n":"Substitute","t":"Normal","c":"T","bp":0,"a":101,"p":0},"subzeroslammer":{"n":"Subzero Slammer","t":"Ice","c":"P","bp":1,"a":101,"p":0},"suckerpunch":{"n":"Sucker Punch","t":"Dark","c":"P","bp":70,"a":100,"p":1,"sucker":true,"ct":true},"sunnyday":{"n":"Sunny Day","t":"Fire","c":"T","bp":0,"a":101,"p":0},"sunsteelstrike":{"n":"Sunsteel Strike","t":"Steel","c":"P","bp":100,"a":100,"p":0,"ct":true},"supercellslam":{"n":"Supercell Slam","t":"Electric","c":"P","bp":100,"a":95,"p":0,"ct":true},"superfang":{"n":"Super Fang","t":"Normal","c":"P","bp":0,"a":90,"p":0,"ct":true},"superpower":{"n":"Superpower","t":"Fighting","c":"P","bp":120,"a":100,"p":0,"ct":true,"sb":{"def":-1,"spd":-1}},"supersonic":{"n":"Supersonic","t":"Normal","c":"T","bp":0,"a":55,"p":0},"supersonicskystrike":{"n":"Supersonic Skystrike","t":"Flying","c":"P","bp":1,"a":101,"p":0},"surf":{"n":"Surf","t":"Water","c":"S","bp":90,"a":100,"p":0},"surgingstrikes":{"n":"Surging Strikes","t":"Water","c":"P","bp":25,"a":100,"p":0,"mh":3,"ct":true},"swagger":{"n":"Swagger","t":"Normal","c":"T","bp":0,"a":85,"p":0},"swallow":{"n":"Swallow","t":"Normal","c":"T","bp":0,"a":101,"p":0},"sweetkiss":{"n":"Sweet Kiss","t":"Fairy","c":"T","bp":0,"a":75,"p":0},"sweetscent":{"n":"Sweet Scent","t":"Normal","c":"T","bp":0,"a":100,"p":0},"swift":{"n":"Swift","t":"Normal","c":"S","bp":60,"a":101,"p":0},"switcheroo":{"n":"Switcheroo","t":"Dark","c":"T","bp":0,"a":100,"p":0},"swordsdance":{"n":"Swords Dance","t":"Normal","c":"T","bp":0,"a":101,"p":0},"synchronoise":{"n":"Synchronoise","t":"Psychic","c":"S","bp":120,"a":100,"p":0},"synthesis":{"n":"Synthesis","t":"Grass","c":"T","bp":0,"a":101,"p":0},"syrupbomb":{"n":"Syrup Bomb","t":"Grass","c":"S","bp":60,"a":85,"p":0},"tachyoncutter":{"n":"Tachyon Cutter","t":"Steel","c":"S","bp":50,"a":101,"p":0,"mh":2},"tackle":{"n":"Tackle","t":"Normal","c":"P","bp":40,"a":100,"p":0,"ct":true},"tailglow":{"n":"Tail Glow","t":"Bug","c":"T","bp":0,"a":101,"p":0},"tailslap":{"n":"Tail Slap","t":"Normal","c":"P","bp":25,"a":85,"p":0,"mh":[2,5],"ct":true},"tailwhip":{"n":"Tail Whip","t":"Normal","c":"T","bp":0,"a":100,"p":0},"tailwind":{"n":"Tailwind","t":"Flying","c":"T","bp":0,"a":101,"p":0},"takedown":{"n":"Take Down","t":"Normal","c":"P","bp":90,"a":85,"p":0,"ct":true,"rc":[1,4]},"takeheart":{"n":"Take Heart","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"tarshot":{"n":"Tar Shot","t":"Rock","c":"T","bp":0,"a":100,"p":0},"taunt":{"n":"Taunt","t":"Dark","c":"T","bp":0,"a":100,"p":0},"tearfullook":{"n":"Tearful Look","t":"Normal","c":"T","bp":0,"a":101,"p":0},"teatime":{"n":"Teatime","t":"Normal","c":"T","bp":0,"a":101,"p":0},"technoblast":{"n":"Techno Blast","t":"Normal","c":"S","bp":120,"a":100,"p":0},"tectonicrage":{"n":"Tectonic Rage","t":"Ground","c":"P","bp":1,"a":101,"p":0},"teeterdance":{"n":"Teeter Dance","t":"Normal","c":"T","bp":0,"a":100,"p":0},"telekinesis":{"n":"Telekinesis","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"teleport":{"n":"Teleport","t":"Psychic","c":"T","bp":0,"a":101,"p":-6},"temperflare":{"n":"Temper Flare","t":"Fire","c":"P","bp":75,"a":100,"p":0,"ct":true},"terablast":{"n":"Tera Blast","t":"Normal","c":"S","bp":80,"a":100,"p":0},"terastarstorm":{"n":"Tera Starstorm","t":"Normal","c":"S","bp":120,"a":100,"p":0},"terrainpulse":{"n":"Terrain Pulse","t":"Normal","c":"S","bp":50,"a":100,"p":0},"thief":{"n":"Thief","t":"Dark","c":"P","bp":60,"a":100,"p":0,"ct":true},"thousandarrows":{"n":"Thousand Arrows","t":"Ground","c":"P","bp":90,"a":100,"p":0},"thousandwaves":{"n":"Thousand Waves","t":"Ground","c":"P","bp":90,"a":100,"p":0},"thrash":{"n":"Thrash","t":"Normal","c":"P","bp":120,"a":100,"p":0,"ct":true},"throatchop":{"n":"Throat Chop","t":"Dark","c":"P","bp":80,"a":100,"p":0,"ct":true},"thunder":{"n":"Thunder","t":"Electric","c":"S","bp":110,"a":70,"p":0},"thunderbolt":{"n":"Thunderbolt","t":"Electric","c":"S","bp":90,"a":100,"p":0},"thundercage":{"n":"Thunder Cage","t":"Electric","c":"S","bp":80,"a":90,"p":0},"thunderclap":{"n":"Thunderclap","t":"Electric","c":"S","bp":70,"a":100,"p":1},"thunderfang":{"n":"Thunder Fang","t":"Electric","c":"P","bp":65,"a":95,"p":0,"ct":true},"thunderouskick":{"n":"Thunderous Kick","t":"Fighting","c":"P","bp":90,"a":100,"p":0,"ct":true},"thunderpunch":{"n":"Thunder Punch","t":"Electric","c":"P","bp":75,"a":100,"p":0,"ct":true},"thundershock":{"n":"Thunder Shock","t":"Electric","c":"S","bp":40,"a":100,"p":0},"thunderwave":{"n":"Thunder Wave","t":"Electric","c":"T","bp":0,"a":90,"p":0},"tickle":{"n":"Tickle","t":"Normal","c":"T","bp":0,"a":100,"p":0},"tidyup":{"n":"Tidy Up","t":"Normal","c":"T","bp":0,"a":101,"p":0},"topsyturvy":{"n":"Topsy-Turvy","t":"Dark","c":"T","bp":0,"a":101,"p":0},"torchsong":{"n":"Torch Song","t":"Fire","c":"S","bp":80,"a":100,"p":0},"torment":{"n":"Torment","t":"Dark","c":"T","bp":0,"a":100,"p":0},"toxic":{"n":"Toxic","t":"Poison","c":"T","bp":0,"a":90,"p":0},"toxicspikes":{"n":"Toxic Spikes","t":"Poison","c":"T","bp":0,"a":101,"p":0},"toxicthread":{"n":"Toxic Thread","t":"Poison","c":"T","bp":0,"a":100,"p":0},"trailblaze":{"n":"Trailblaze","t":"Grass","c":"P","bp":50,"a":100,"p":0,"ct":true},"transform":{"n":"Transform","t":"Normal","c":"T","bp":0,"a":101,"p":0},"triattack":{"n":"Tri Attack","t":"Normal","c":"S","bp":80,"a":100,"p":0},"trick":{"n":"Trick","t":"Psychic","c":"T","bp":0,"a":100,"p":0},"trickortreat":{"n":"Trick-or-Treat","t":"Ghost","c":"T","bp":0,"a":100,"p":0},"trickroom":{"n":"Trick Room","t":"Psychic","c":"T","bp":0,"a":101,"p":-7},"triplearrows":{"n":"Triple Arrows","t":"Fighting","c":"P","bp":90,"a":100,"p":0},"tripleaxel":{"n":"Triple Axel","t":"Ice","c":"P","bp":20,"a":90,"p":0,"mh":3,"ct":true},"tripledive":{"n":"Triple Dive","t":"Water","c":"P","bp":30,"a":95,"p":0,"mh":3,"ct":true},"triplekick":{"n":"Triple Kick","t":"Fighting","c":"P","bp":10,"a":90,"p":0,"mh":3,"ct":true},"tropkick":{"n":"Trop Kick","t":"Grass","c":"P","bp":70,"a":100,"p":0,"ct":true},"trumpcard":{"n":"Trump Card","t":"Normal","c":"S","bp":0,"a":101,"p":0,"ct":true},"twinbeam":{"n":"Twin Beam","t":"Psychic","c":"S","bp":40,"a":100,"p":0,"mh":2},"twineedle":{"n":"Twineedle","t":"Bug","c":"P","bp":25,"a":100,"p":0,"mh":2},"twinkletackle":{"n":"Twinkle Tackle","t":"Fairy","c":"P","bp":1,"a":101,"p":0},"twister":{"n":"Twister","t":"Dragon","c":"S","bp":40,"a":100,"p":0},"upperhand":{"n":"Upper Hand","t":"Fighting","c":"P","bp":65,"a":100,"p":3,"ct":true},"uproar":{"n":"Uproar","t":"Normal","c":"S","bp":90,"a":100,"p":0},"uturn":{"n":"U-turn","t":"Bug","c":"P","bp":70,"a":100,"p":0,"ct":true},"vacuumwave":{"n":"Vacuum Wave","t":"Fighting","c":"S","bp":40,"a":100,"p":1},"vcreate":{"n":"V-create","t":"Fire","c":"P","bp":180,"a":95,"p":0,"ct":true,"sb":{"spe":-1,"def":-1,"spd":-1}},"veeveevolley":{"n":"Veevee Volley","t":"Normal","c":"P","bp":0,"a":101,"p":0,"ct":true},"venomdrench":{"n":"Venom Drench","t":"Poison","c":"T","bp":0,"a":100,"p":0},"venoshock":{"n":"Venoshock","t":"Poison","c":"S","bp":65,"a":100,"p":0},"victorydance":{"n":"Victory Dance","t":"Fighting","c":"T","bp":0,"a":101,"p":0},"vinewhip":{"n":"Vine Whip","t":"Grass","c":"P","bp":45,"a":100,"p":0,"ct":true},"visegrip":{"n":"Vise Grip","t":"Normal","c":"P","bp":55,"a":100,"p":0,"ct":true},"vitalthrow":{"n":"Vital Throw","t":"Fighting","c":"P","bp":70,"a":101,"p":-1,"ct":true},"voltswitch":{"n":"Volt Switch","t":"Electric","c":"S","bp":70,"a":100,"p":0},"volttackle":{"n":"Volt Tackle","t":"Electric","c":"P","bp":120,"a":100,"p":0,"ct":true,"rc":[33,100]},"wakeupslap":{"n":"Wake-Up Slap","t":"Fighting","c":"P","bp":70,"a":100,"p":0,"ct":true},"waterfall":{"n":"Waterfall","t":"Water","c":"P","bp":80,"a":100,"p":0,"ct":true},"watergun":{"n":"Water Gun","t":"Water","c":"S","bp":40,"a":100,"p":0},"waterpledge":{"n":"Water Pledge","t":"Water","c":"S","bp":80,"a":100,"p":0},"waterpulse":{"n":"Water Pulse","t":"Water","c":"S","bp":60,"a":100,"p":0},"watershuriken":{"n":"Water Shuriken","t":"Water","c":"S","bp":15,"a":100,"p":1,"mh":[2,5]},"watersport":{"n":"Water Sport","t":"Water","c":"T","bp":0,"a":101,"p":0},"waterspout":{"n":"Water Spout","t":"Water","c":"S","bp":150,"a":100,"p":0},"wavecrash":{"n":"Wave Crash","t":"Water","c":"P","bp":120,"a":100,"p":0,"ct":true,"rc":[33,100]},"weatherball":{"n":"Weather Ball","t":"Normal","c":"S","bp":50,"a":100,"p":0},"whirlpool":{"n":"Whirlpool","t":"Water","c":"S","bp":35,"a":85,"p":0},"whirlwind":{"n":"Whirlwind","t":"Normal","c":"T","bp":0,"a":101,"p":-6},"wickedblow":{"n":"Wicked Blow","t":"Dark","c":"P","bp":75,"a":100,"p":0,"ct":true},"wickedtorque":{"n":"Wicked Torque","t":"Dark","c":"P","bp":80,"a":100,"p":0},"wideguard":{"n":"Wide Guard","t":"Rock","c":"T","bp":0,"a":101,"p":3},"wildboltstorm":{"n":"Wildbolt Storm","t":"Electric","c":"S","bp":100,"a":80,"p":0},"wildcharge":{"n":"Wild Charge","t":"Electric","c":"P","bp":90,"a":100,"p":0,"ct":true,"rc":[1,4]},"willowisp":{"n":"Will-O-Wisp","t":"Fire","c":"T","bp":0,"a":85,"p":0},"wingattack":{"n":"Wing Attack","t":"Flying","c":"P","bp":60,"a":100,"p":0,"ct":true},"wish":{"n":"Wish","t":"Normal","c":"T","bp":0,"a":101,"p":0},"withdraw":{"n":"Withdraw","t":"Water","c":"T","bp":0,"a":101,"p":0},"wonderroom":{"n":"Wonder Room","t":"Psychic","c":"T","bp":0,"a":101,"p":0},"woodhammer":{"n":"Wood Hammer","t":"Grass","c":"P","bp":120,"a":100,"p":0,"ct":true,"rc":[33,100]},"workup":{"n":"Work Up","t":"Normal","c":"T","bp":0,"a":101,"p":0},"worryseed":{"n":"Worry Seed","t":"Grass","c":"T","bp":0,"a":100,"p":0},"wrap":{"n":"Wrap","t":"Normal","c":"P","bp":15,"a":90,"p":0,"ct":true},"wringout":{"n":"Wring Out","t":"Normal","c":"S","bp":0,"a":100,"p":0,"ct":true},"xscissor":{"n":"X-Scissor","t":"Bug","c":"P","bp":80,"a":100,"p":0,"ct":true},"yawn":{"n":"Yawn","t":"Normal","c":"T","bp":0,"a":101,"p":0},"zapcannon":{"n":"Zap Cannon","t":"Electric","c":"S","bp":120,"a":50,"p":0},"zenheadbutt":{"n":"Zen Headbutt","t":"Psychic","c":"P","bp":80,"a":90,"p":0,"ct":true},"zingzap":{"n":"Zing Zap","t":"Electric","c":"P","bp":80,"a":100,"p":0,"ct":true},"zippyzap":{"n":"Zippy Zap","t":"Electric","c":"P","bp":80,"a":100,"p":2,"ct":true},"paleowave":{"n":"Paleo Wave","t":"Rock","c":"S","bp":85,"a":100,"p":0},"shadowstrike":{"n":"Shadow Strike","t":"Ghost","c":"P","bp":80,"a":95,"p":0,"ct":true},"polarflare":{"n":"Polar Flare","t":"Fire","c":"S","bp":75,"a":100,"p":0}},"types":{"Normal":{"Normal":1,"Fire":1,"Water":1,"Grass":1,"Electric":1,"Ice":1,"Fighting":1,"Poison":1,"Ground":1,"Flying":1,"Psychic":1,"Bug":1,"Rock":0.5,"Ghost":0,"Dragon":1,"Steel":0.5,"Fairy":1,"Dark":1},"Fire":{"Normal":1,"Fire":0.5,"Water":0.5,"Grass":2,"Electric":1,"Ice":2,"Fighting":1,"Poison":1,"Ground":1,"Flying":1,"Psychic":1,"Bug":2,"Rock":0.5,"Ghost":1,"Dragon":0.5,"Steel":2,"Fairy":1,"Dark":1},"Water":{"Normal":1,"Fire":2,"Water":0.5,"Grass":0.5,"Electric":1,"Ice":1,"Fighting":1,"Poison":1,"Ground":2,"Flying":1,"Psychic":1,"Bug":1,"Rock":2,"Ghost":1,"Dragon":0.5,"Steel":1,"Fairy":1,"Dark":1},"Grass":{"Normal":1,"Fire":0.5,"Water":2,"Grass":0.5,"Electric":1,"Ice":1,"Fighting":1,"Poison":0.5,"Ground":2,"Flying":0.5,"Psychic":1,"Bug":0.5,"Rock":2,"Ghost":1,"Dragon":0.5,"Steel":0.5,"Fairy":1,"Dark":1},"Electric":{"Normal":1,"Fire":1,"Water":2,"Grass":0.5,"Electric":0.5,"Ice":1,"Fighting":1,"Poison":1,"Ground":0,"Flying":2,"Psychic":1,"Bug":1,"Rock":1,"Ghost":1,"Dragon":0.5,"Steel":1,"Fairy":1,"Dark":1},"Ice":{"Normal":1,"Fire":0.5,"Water":0.5,"Grass":2,"Electric":1,"Ice":0.5,"Fighting":1,"Poison":1,"Ground":2,"Flying":2,"Psychic":1,"Bug":1,"Rock":1,"Ghost":1,"Dragon":2,"Steel":0.5,"Fairy":1,"Dark":1},"Fighting":{"Normal":2,"Fire":1,"Water":1,"Grass":1,"Electric":1,"Ice":2,"Fighting":1,"Poison":0.5,"Ground":1,"Flying":0.5,"Psychic":0.5,"Bug":0.5,"Rock":2,"Ghost":0,"Dragon":1,"Steel":2,"Fairy":0.5,"Dark":2},"Poison":{"Normal":1,"Fire":1,"Water":1,"Grass":2,"Electric":1,"Ice":1,"Fighting":1,"Poison":0.5,"Ground":0.5,"Flying":1,"Psychic":1,"Bug":1,"Rock":0.5,"Ghost":0.5,"Dragon":1,"Steel":0,"Fairy":2,"Dark":1},"Ground":{"Normal":1,"Fire":2,"Water":1,"Grass":0.5,"Electric":2,"Ice":1,"Fighting":1,"Poison":2,"Ground":1,"Flying":0,"Psychic":1,"Bug":0.5,"Rock":2,"Ghost":1,"Dragon":1,"Steel":2,"Fairy":1,"Dark":1},"Flying":{"Normal":1,"Fire":1,"Water":1,"Grass":2,"Electric":0.5,"Ice":1,"Fighting":2,"Poison":1,"Ground":1,"Flying":1,"Psychic":1,"Bug":2,"Rock":0.5,"Ghost":1,"Dragon":1,"Steel":0.5,"Fairy":1,"Dark":1},"Psychic":{"Normal":1,"Fire":1,"Water":1,"Grass":1,"Electric":1,"Ice":1,"Fighting":2,"Poison":2,"Ground":1,"Flying":1,"Psychic":0.5,"Bug":1,"Rock":1,"Ghost":1,"Dragon":1,"Steel":0.5,"Fairy":1,"Dark":0},"Bug":{"Normal":1,"Fire":0.5,"Water":1,"Grass":2,"Electric":1,"Ice":1,"Fighting":0.5,"Poison":0.5,"Ground":1,"Flying":0.5,"Psychic":2,"Bug":1,"Rock":1,"Ghost":0.5,"Dragon":1,"Steel":0.5,"Fairy":0.5,"Dark":2},"Rock":{"Normal":1,"Fire":2,"Water":1,"Grass":1,"Electric":1,"Ice":2,"Fighting":0.5,"Poison":1,"Ground":0.5,"Flying":2,"Psychic":1,"Bug":2,"Rock":1,"Ghost":1,"Dragon":1,"Steel":0.5,"Fairy":1,"Dark":1},"Ghost":{"Normal":0,"Fire":1,"Water":1,"Grass":1,"Electric":1,"Ice":1,"Fighting":1,"Poison":1,"Ground":1,"Flying":1,"Psychic":2,"Bug":1,"Rock":1,"Ghost":2,"Dragon":1,"Steel":1,"Fairy":1,"Dark":0.5},"Dragon":{"Normal":1,"Fire":1,"Water":1,"Grass":1,"Electric":1,"Ice":1,"Fighting":1,"Poison":1,"Ground":1,"Flying":1,"Psychic":1,"Bug":1,"Rock":1,"Ghost":1,"Dragon":2,"Steel":0.5,"Fairy":0,"Dark":1},"Steel":{"Normal":1,"Fire":0.5,"Water":0.5,"Grass":1,"Electric":0.5,"Ice":2,"Fighting":1,"Poison":1,"Ground":1,"Flying":1,"Psychic":1,"Bug":1,"Rock":2,"Ghost":1,"Dragon":1,"Steel":0.5,"Fairy":2,"Dark":1},"Fairy":{"Normal":1,"Fire":0.5,"Water":1,"Grass":1,"Electric":1,"Ice":1,"Fighting":2,"Poison":0.5,"Ground":1,"Flying":1,"Psychic":1,"Bug":1,"Rock":1,"Ghost":1,"Dragon":2,"Steel":0.5,"Fairy":1,"Dark":2},"Dark":{"Normal":1,"Fire":1,"Water":1,"Grass":1,"Electric":1,"Ice":1,"Fighting":0.5,"Poison":1,"Ground":1,"Flying":1,"Psychic":2,"Bug":1,"Rock":1,"Ghost":2,"Dragon":1,"Steel":1,"Fairy":0.5,"Dark":0.5}}}''')
MY_TEAM = json.loads(r'''[{"name": "Dragapult", "item": "Choice Band", "ability": "Infiltrator", "nature": "jolly", "evs": [0, 252, 0, 0, 4, 252], "moves": ["Dragon Darts", "Phantom Force", "Flamethrower", "U-turn"]}, {"name": "Greninja", "item": "Focus Sash", "ability": "Protean", "nature": "timid", "evs": [0, 0, 0, 252, 4, 252], "moves": ["Ice Beam", "Dark Pulse", "Hydro Pump", "Water Shuriken"]}, {"name": "Scizor", "item": "Metal Coat", "ability": "Technician", "nature": "adamant", "evs": [252, 252, 0, 0, 4, 0], "moves": ["Bullet Punch", "Close Combat", "Knock Off", "Swords Dance"]}]''')
TEAM_ORDER = "123"
PARAMS = json.loads(r'''{"foe_switch_low": 0.12, "foe_switch": 0.05, "w_race": 0.25, "lam_worst": 0.3, "switch_margin": 0.1, "q_other": 0.04, "q_default": 0.85, "lock_pen": 0.15, "switch_cost": 0.03, "w_mat": 1.0, "scarf_prob": 0.07, "foe_greedy": 0.72, "ko_bonus": 0.2}''')

SP = DATA["species"]
MV = DATA["moves"]
TC = DATA["types"]
LVL = 100

NATURES = {
    "adamant": ("atk", "spa"), "jolly": ("spe", "spa"), "modest": ("spa", "atk"), "timid": ("spe", "atk"),
    "bold": ("def", "atk"), "calm": ("spd", "atk"), "impish": ("def", "spa"), "careful": ("spd", "spa"),
    "naive": ("spe", "spd"), "hasty": ("spe", "def"), "relaxed": ("def", "spe"),
}
STATS = ["hp", "atk", "def", "spa", "spd", "spe"]
PRIORITY_FOE_FIRST_TURN = {"fakeout", "firstimpression"}
HEAL_MOVES = {"roost", "recover", "morningsun", "synthesis", "softboiled", "slackoff", "wish", "rest"}
SETUP = {
    "swordsdance": {"atk": 2}, "dragondance": {"atk": 1, "spe": 1}, "nastyplot": {"spa": 2},
    "quiverdance": {"spa": 1, "spd": 1, "spe": 1}, "calmmind": {"spa": 1, "spd": 1}, "bulkup": {"atk": 1, "def": 1},
    "irondefense": {"def": 2}, "agility": {"spe": 2}, "growth": {"atk": 1, "spa": 1}, "curse": {"atk": 1, "def": 1},
}
STATUS_MOVES = {
    "willowisp": ("brn", 85), "thunderwave": ("par", 90), "sleeppowder": ("slp", 75), "toxic": ("psn", 90),
    "yawn": ("slp", 60), "leechseed": ("seed", 90)
}
OHKO_BAD = {"explosion"}

SPECIES_ITEM_PRIOR = {
    "gengar": {"choicescarf": 0.35, "focussash": 0.35, "lifeorb": 0.30},
    "excadrill": {"focussash": 0.50, "choicescarf": 0.30, "lifeorb": 0.20},
    "hydreigon": {"choicespecs": 0.50, "choicescarf": 0.35, "lifeorb": 0.15},
    "togekiss": {"leftovers": 0.60, "choicescarf": 0.30, "heavydutyboots": 0.10},
    "garchomp": {"lifeorb": 0.50, "choicescarf": 0.25, "focussash": 0.15, "leftovers": 0.10},
    "alakazam": {"focussash": 0.60, "lifeorb": 0.40},
    "dragapult": {"choiceband": 0.45, "choicespecs": 0.30, "lifeorb": 0.25},
    "volcarona": {"heavydutyboots": 0.85, "focussash": 0.15},
    "arcanine": {"heavydutyboots": 0.80, "leftovers": 0.20},
    "dragonite": {"lumberry": 0.50, "weaknesspolicy": 0.30, "heavydutyboots": 0.20},
    "metagross": {"assaultvest": 0.80, "choiceband": 0.20},
    "scizor": {"metalcoat": 0.45, "choiceband": 0.35, "lifeorb": 0.20},
    "ferrothorn": {"leftovers": 0.65, "rockyhelmet": 0.35},
    "corviknight": {"leftovers": 0.65, "rockyhelmet": 0.35},
    "lapras": {"assaultvest": 0.60, "leftovers": 0.40},
    "snorlax": {"assaultvest": 0.50, "leftovers": 0.50},
    "blastoise": {"leftovers": 0.70, "lifeorb": 0.30},
    "venusaur": {"blacksludge": 0.80, "lifeorb": 0.20},
    "charizard": {"choicespecs": 0.50, "heavydutyboots": 0.30, "lifeorb": 0.20},
    "lucario": {"lifeorb": 0.60, "focussash": 0.30, "choiceband": 0.10},
    "gyarados": {"leftovers": 0.50, "lifeorb": 0.30, "lumberry": 0.20},
    "tyranitar": {"leftovers": 0.50, "choiceband": 0.30, "assaultvest": 0.20},
    "greninja": {"lifeorb": 0.50, "focussash": 0.35, "choicespecs": 0.15},
    "cloyster": {"focussash": 0.80, "lifeorb": 0.20}
}



def norm(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def boost_mult(s):
    s = max(-6, min(6, int(s or 0)))
    return (2 + s) / 2.0 if s >= 0 else 2.0 / (2 - s)


def calc_stats(name, evs, nature):
    b = SP[name]["b"]
    up, down = NATURES.get(nature, (None, None))
    out = {}
    for i, st in enumerate(STATS):
        base = b[i]
        ev = evs[i]
        if st == "hp":
            out[st] = (2 * base + 31 + ev // 4) * LVL // 100 + LVL + 10
        else:
            v = (2 * base + 31 + ev // 4) * LVL // 100 + 5
            m = 1.1 if st == up else (0.9 if st == down else 1.0)
            out[st] = int(v * m)
    return out


def type_eff(mt, types):
    e = 1.0
    row = TC.get(mt)
    if not row:
        return 1.0
    for t in types:
        e *= row.get(t, 1.0)
    return e


def move_info(mid, obs_mv=None):
    """Move record from DB; falls back to whatever the observation says."""
    m = MV.get(norm(mid))
    if m is None and obs_mv is not None:
        cat = str(obs_mv.get("category", "Physical"))[:1].upper()
        cat = {"P": "P", "S": "S"}.get(cat, "T")
        if str(obs_mv.get("category", "")).lower().startswith("stat"):
            cat = "T"
        acc = obs_mv.get("accuracy", 100)
        acc = 101 if acc is True or acc is None else int(acc)
        m = {
            "n": obs_mv.get("name", str(mid)), "t": obs_mv.get("type", "Normal"), "c": cat,
            "bp": int(obs_mv.get("base_power") or 0), "a": acc, "p": 0
        }
    return m


# ---------------------------------------------------------------------------
# Mon model
# ---------------------------------------------------------------------------
class Mon:
    __slots__ = ("name", "types", "stats", "maxhp", "hp", "item", "ability", "status", "boosts", "moves",
                 "ab_probs", "item_prob", "known")

    def __init__(self, name, stats, hp_frac, item, ability, moves, status="", boosts=None, ab_probs=None,
                 item_prob=1.0, known=True):
        self.name = name
        self.types = SP[name]["t"]
        self.stats = stats
        self.maxhp = stats["hp"]
        self.hp = max(0.0, self.maxhp * hp_frac)
        self.item = item
        self.ability = ability
        self.status = status
        self.boosts = boosts or {}
        self.moves = moves
        self.ab_probs = ab_probs or [(ability, 1.0)]
        self.item_prob = item_prob
        self.known = known

    @property
    def frac(self):
        return self.hp / self.maxhp if self.maxhp else 0.0


def my_mon_from_set(sset, hp_frac, status=""):
    name = sset["name"]
    evs = sset["evs"]
    stats = calc_stats(name, evs, sset["nature"])
    return Mon(name, stats, hp_frac, norm(sset["item"]), norm(sset["ability"]), [norm(m) for m in sset["moves"]], status)


def foe_mon_from_name(name, hp_frac, status="", boosts=None):
    p = SP[name]
    stats = calc_stats(name, p["evs"], p["nature"])
    abil = p["ab"]
    if len(abil) == 1:
        probs = [(abil[0], 1.0)]
    else:
        probs = [(abil[0], 0.65)] + [(a, 0.35 / (len(abil) - 1)) for a in abil[1:]]
    return Mon(name, stats, hp_frac, p["item"], abil[0], list(p["dm"]), status, boosts, probs, 0.6, False)


# ---------------------------------------------------------------------------
# Damage calculation
# ---------------------------------------------------------------------------
def eff_speed(m, weather="", scarf_prob=0.0):
    if isinstance(weather, bool):
        weather = "sand" if weather else ""
    s = m.stats["spe"] * boost_mult(m.boosts.get("spe", 0))
    if m.status == "par":
        s *= 0.5
    if m.item == "choicescarf":
        s *= 1.5
    if weather == "sand" and any(a == "sandrush" and p >= 0.5 for a, p in m.ab_probs):
        s *= 2
    elif weather == "sun" and any(a == "chlorophyll" and p >= 0.5 for a, p in m.ab_probs):
        s *= 2
    elif weather == "rain" and any(a == "swiftswim" and p >= 0.5 for a, p in m.ab_probs):
        s *= 2
    elif weather in ("snow", "hail") and any(a == "slushrush" and p >= 0.5 for a, p in m.ab_probs):
        s *= 2
    return s


def ability_mult(att, dfn, mv, ab, atk_ab):
    """Defender ability multiplier for a move (immunities etc)."""
    t = mv["t"]
    if atk_ab == "moldbreaker":
        return 1.0
    if ab == "levitate" and t == "Ground":
        return 0.0
    if ab == "flashfire" and t == "Fire":
        return 0.0
    if ab in ("waterabsorb", "stormdrain") and t == "Water":
        return 0.0
    if ab == "voltabsorb" and t == "Electric":
        return 0.0
    if ab == "thickfat" and t in ("Fire", "Ice"):
        return 0.5
    if ab == "multiscale" and dfn.hp >= dfn.maxhp - 0.5:
        return 0.5
    return 1.0


_cache = {}


def damage_rolls(att, dfn, mid, weather=""):
    """16 damage rolls (absolute HP) of move mid from att to dfn."""
    mv = MV.get(mid)
    if mv is None or mv["c"] == "T":
        return [0.0] * 16
    if isinstance(weather, bool):
        weather = "sand" if weather else ""
    key = (
        att.name, att.hp > 0, round(att.frac, 2), tuple(sorted(att.boosts.items())), att.status, att.item, att.ability,
        dfn.name, round(dfn.frac, 2), tuple(sorted(dfn.boosts.items())), dfn.status, dfn.item, mid, weather, att.stats["atk"], dfn.stats["def"]
    )
    r = _cache.get(key)
    if r is not None:
        return r

    cat = mv["c"]
    bp = mv["bp"]
    types_def = dfn.types
    mt = mv["t"]
    if mv.get("speedbp") == "gyroball":
        bp = min(150, int(25 * eff_speed(dfn, weather) / max(1, eff_speed(att, weather))) + 1)
    if mv.get("knock"):
        has_item = bool(dfn.item and dfn.item != "none" and dfn.item_prob > 0.1)
        bp = 97 if has_item else 65
    if mv.get("cond") == "facade" and att.status:
        bp *= 2
    if att.ability == "technician" and bp <= 60:
        bp = bp * 1.5

    mh = mv.get("mh")
    hits = 1
    if mh:
        hits = mh if isinstance(mh, int) else (3.1 if mh == [2, 5] else sum(mh) / 2.0)

    if mv.get("bodypress"):
        A = att.stats["def"] * boost_mult(att.boosts.get("def", 0))
    elif cat == "P":
        A = att.stats["atk"] * boost_mult(att.boosts.get("atk", 0))
        if mv.get("foulplay"):
            A = dfn.stats["atk"] * boost_mult(dfn.boosts.get("atk", 0))
    else:
        A = att.stats["spa"] * boost_mult(att.boosts.get("spa", 0))

    if cat == "P" or mv.get("ods") == "def":
        D = dfn.stats["def"] * boost_mult(dfn.boosts.get("def", 0))
        if weather == "snow" and "Ice" in types_def:
            D *= 1.5
    else:
        D = dfn.stats["spd"] * boost_mult(dfn.boosts.get("spd", 0))
        if weather == "sand" and "Rock" in types_def:
            D *= 1.5

    if cat == "S" and dfn.item == "assaultvest":
        D *= 1.0 + 0.5 * dfn.item_prob

    mod = 1.0
    it = att.item
    ip = att.item_prob
    if it == "lifeorb":
        mod *= 1 + 0.3 * ip
    elif it == "choiceband" and cat == "P":
        mod *= 1 + 0.5 * ip
    elif it == "choicespecs" and cat == "S":
        mod *= 1 + 0.5 * ip
    elif it == "metalcoat" and mt == "Steel":
        mod *= 1 + 0.2 * ip

    if weather == "rain":
        if mt == "Water":
            mod *= 1.5
        elif mt == "Fire":
            mod *= 0.5
    elif weather == "sun":
        if mt == "Fire":
            mod *= 1.5
        elif mt == "Water":
            mod *= 0.5

    if mid == "solarbeam" and weather in ("rain", "sand", "snow"):
        mod *= 0.5

    if mid == "freezedry":
        eff = 1.0
        for t in types_def:
            e = TC["Ice"].get(t, 1.0)
            eff *= 2.0 if t == "Water" else e
    else:
        eff = type_eff(mt, types_def)

    if eff == 0:
        _cache[key] = [0.0] * 16
        return _cache[key]

    stab = 1.5 if (mt in att.types or att.ability == "protean") else 1.0
    if att.status == "brn" and cat == "P" and att.ability != "guts":
        mod *= 0.5

    if att.hp <= att.maxhp / 3.0:
        for ab, pb in att.ab_probs:
            if (ab == "blaze" and mt == "Fire") or (ab == "torrent" and mt == "Water") or (ab == "overgrow" and mt == "Grass") or (ab == "swarm" and mt == "Bug"):
                mod *= 1 + 0.5 * pb

    base = int(int(int(2 * LVL / 5 + 2) * bp * A / max(1.0, D)) / 50) + 2

    am = 0.0
    for ab, pb in dfn.ab_probs:
        am += pb * ability_mult(att, dfn, mv, ab, att.ability)

    rolls = []
    for r in range(85, 101):
        d = int(base * r / 100.0)
        d = d * stab * eff * mod * am
        rolls.append(float(int(d)) * hits)

    _cache[key] = rolls
    return rolls


def roll_samples(rolls):
    """Compress 16 rolls to 3 weighted samples (low, mid, high)."""
    return ((rolls[1], 0.3), (rolls[8], 0.4), (rolls[14], 0.3))


# ---------------------------------------------------------------------------
# Memory & State
# ---------------------------------------------------------------------------
class FoeMemory:
    def __init__(self):
        self.seen = set()
        self.inferred = {}
        self.turns_active = 0
        self.speed_lo = 0.0
        self.speed_hi = 1e9
        self.item_known = None
        self.ability_known = None


class PokemonAgent:
    def __init__(self):
        self.reset()

    def reset(self):
        self.foe_mem = {}
        self.prev = None
        self.prev_action = None
        self.last_turn = -1
        self.foe_team_hp = {}
        self.weather = ""
        self.sand_turns = 0
        self.my_known_stats = {}
        self.my_seen_hp = {}
        self.foe_switch_turn = 0
        self.errors = 0

    def decide(self, observation):
        try:
            a = self._decide(observation)
            if self._legal(observation, a):
                return a
        except Exception:
            self.errors += 1
        return self._fallback(observation)

    def _legal(self, obs, a):
        if obs.get("team_preview"):
            return isinstance(a, str) and a.startswith("team ")
        if a == "pass":
            return True
        moves = {"move %d" % m.get("index", 0) for m in obs.get("valid_moves", []) or []}
        sw = {"switch %d" % s.get("index", 0) for s in obs.get("valid_switches", []) or []}
        if obs.get("force_switch"):
            return a in sw
        return a in moves or a in sw

    def _fallback(self, obs):
        if obs.get("team_preview"):
            return "team " + TEAM_ORDER
        sw = obs.get("valid_switches", []) or []
        mv = obs.get("valid_moves", []) or []
        if obs.get("force_switch"):
            if sw:
                best = max(sw, key=lambda s: s.get("hp_percent", 0))
                return "switch %d" % best.get("index", sw[0].get("index", 2))
            return "pass"
        if mv:
            try:
                best = max(mv, key=lambda m: (m.get("base_power") or 0) * m.get("type_multiplier", 1.0) * (1.5 if m.get("stab") else 1.0))
                return "move %d" % best.get("index", 1)
            except Exception:
                return "move %d" % mv[0].get("index", 1)
        if sw:
            return "switch %d" % sw[0].get("index", 2)
        return "pass"

    def _decide(self, obs):
        if obs.get("team_preview"):
            return self._decide_team_preview(obs)

        turn = obs.get("turn", 0) or 0
        if turn < self.last_turn:
            self.reset()
        self.last_turn = turn

        my = obs.get("my_active") or {}
        foe = obs.get("foe") or {}
        fname = foe.get("name")
        if fname not in SP:
            return self._fallback(obs)

        self._update_memory(obs)

        me = self._build_my_active(obs)
        foe_m = self._build_foe(obs)
        bench = self._build_bench(obs)

        ctx = Ctx(self, obs, me, foe_m, bench)
        if obs.get("force_switch"):
            choice = ctx.best_forced_switch()
        else:
            choice = ctx.best_action()

        self.prev = {
            "turn": turn, "my_name": my.get("name"), "my_hp": my.get("hp_percent"),
            "foe_name": fname, "foe_hp": foe.get("hp_percent"), "my_maxhp": me.maxhp, "action": choice
        }
        return choice

    def _decide_team_preview(self, obs):
        """Pick optimal lead based on damage calculation matchups if foe team known, otherwise default order."""
        my_team = obs.get("my_team") or obs.get("valid_switches") or []
        foe_team = obs.get("foe_team") or []
        if not foe_team or len(my_team) < 3:
            return "team " + TEAM_ORDER

        foe_names = [p.get("name") for p in foe_team if p.get("name") in SP]
        if not foe_names:
            return "team " + TEAM_ORDER

        has_sand = any(n in ("Tyranitar", "Hippowdon") for n in foe_names)
        foe_mons = [foe_mon_from_name(n, 1.0) for n in foe_names]

        scores = []
        for i, my_p in enumerate(my_team[:3]):
            mname = my_p.get("name")
            if mname not in SP:
                continue
            sset = self._set_for(mname)
            if not sset:
                continue
            me = my_mon_from_set(sset, 1.0)
            has_sash = (me.item == "focussash" and not has_sand)

            total_sc = 0.0
            for foe in foe_mons:
                my_best_dmg = 0.0
                for m in me.moves:
                    mid = norm(m)
                    if mid in MV and MV[mid]["c"] != "T":
                        rl = damage_rolls(me, foe, mid, has_sand)
                        dmg_pct = max(rl) / max(1.0, foe.maxhp)
                        if dmg_pct > my_best_dmg:
                            my_best_dmg = dmg_pct

                foe_best_dmg = 0.0
                for m in foe.moves:
                    mid = norm(m if isinstance(m, str) else m[0])
                    if mid in MV and MV[mid]["c"] != "T":
                        rl = damage_rolls(foe, me, mid, has_sand)
                        dmg_pct = max(rl) / max(1.0, me.maxhp)
                        if dmg_pct > foe_best_dmg:
                            foe_best_dmg = dmg_pct

                faster = (me.stats["spe"] > foe.stats["spe"])

                if faster:
                    if my_best_dmg >= 1.0:
                        sc = 3.0
                    elif my_best_dmg >= 0.5:
                        sc = 1.5 if foe_best_dmg < 1.0 else 0.5
                    else:
                        sc = -1.0 if foe_best_dmg >= 1.0 else 0.0
                else:
                    if has_sash:
                        if my_best_dmg >= 1.0:
                            sc = 2.0
                        else:
                            sc = 0.5
                    else:
                        if foe_best_dmg >= 1.0:
                            sc = -2.5
                        elif my_best_dmg >= 1.0:
                            sc = 2.0
                        else:
                            sc = my_best_dmg - foe_best_dmg

                total_sc += sc
            scores.append((total_sc, i + 1))

        if not scores:
            return "team " + TEAM_ORDER

        scores.sort(key=lambda x: -x[0])
        best_lead = scores[0][1]
        other = [str(x) for x in (1, 2, 3) if x != best_lead]
        return f"team {best_lead}{other[0]}{other[1]}"

    def _set_for(self, name):
        for s in MY_TEAM:
            if s["name"] == name:
                return s
        return None

    def _build_my_active(self, obs):
        my = obs.get("my_active") or {}
        name = my.get("name")
        sset = self._set_for(name)
        hp = (my.get("hp_percent", 100) or 0) / 100.0
        status = self._status_from(my)
        stats = None
        if name in SP:
            st = my.get("stats")
            if isinstance(st, dict) and all(k in st for k in ("atk", "def", "spa", "spd", "spe")):
                mh = self._maxhp_from_condition(my.get("condition"))
                base = calc_stats(name, (sset or {"evs": SP[name]["evs"]})["evs"], (sset or {"nature": SP[name]["nature"]})["nature"])
                stats = {"hp": mh or base["hp"], "atk": st["atk"], "def": st["def"], "spa": st["spa"], "spd": st["spd"], "spe": st["spe"]}
                self.my_known_stats[name] = stats
            elif name in self.my_known_stats:
                stats = self.my_known_stats[name]

        if sset is None:
            sset = {
                "name": name, "item": SP.get(name, {}).get("item", "leftovers"),
                "nature": SP.get(name, {}).get("nature", "adamant"),
                "evs": SP.get(name, {}).get("evs", [0] * 6),
                "ability": SP.get(name, {}).get("ab", [""])[0], "moves": []
            }
        m = my_mon_from_set(sset, hp, status)
        if stats:
            m.stats = stats
            m.maxhp = stats["hp"]
            m.hp = m.maxhp * hp
        m.boosts = dict(my.get("boosts") or {})

        vm = [norm(x.get("id") or x.get("name")) for x in obs.get("valid_moves", []) or []]
        if vm and not obs.get("force_switch"):
            m.moves = vm
            for x in obs.get("valid_moves", []) or []:
                mid = norm(x.get("id") or x.get("name"))
                if mid not in MV:
                    mm = move_info(mid, x)
                    if mm:
                        MV[mid] = mm
        if my.get("item"):
            m.item = norm(my.get("item"))
        if my.get("ability"):
            m.ability = norm(my.get("ability"))
            m.ab_probs = [(m.ability, 1.0)]
        return m

    def _status_from(self, d):
        s = d.get("status") if isinstance(d, dict) else None
        if s:
            return str(s)
        cond = d.get("condition") if isinstance(d, dict) else None
        if isinstance(cond, str):
            parts = cond.split()
            if len(parts) > 1 and parts[1] in ("brn", "par", "slp", "psn", "tox", "frz"):
                return parts[1]
        return ""

    def _maxhp_from_condition(self, cond):
        try:
            return int(str(cond).split()[0].split("/")[1])
        except Exception:
            return None

    def _build_foe(self, obs):
        foe = obs.get("foe") or {}
        name = foe.get("name")
        hp = (foe.get("hp_percent", 100) or 0) / 100.0
        status = str(foe.get("status") or "")
        m = foe_mon_from_name(name, hp, status, dict(foe.get("boosts") or {}))
        mem = self.foe_mem.setdefault(name, FoeMemory())
        m.moves = self._foe_candidates(name, mem)
        if mem.ability_known:
            m.ab_probs = [(mem.ability_known, 1.0)]
        if getattr(mem, "has_no_item", False) or mem.item_known == "none":
            m.item = "none"
            m.item_prob = 0.0
        return m

    def _foe_candidates(self, name, mem):
        """list of (move_id, q) - q = probability foe owns this move."""
        p = SP[name]
        out = {}
        legal = p["legal"]
        defaults = set(p["dm"])
        known = set(mem.seen)
        q_def = PARAMS.get("q_default", 0.85)
        q_oth = PARAMS.get("q_other", 0.04)

        for mid in legal:
            if mid in known:
                out[mid] = 1.0
            elif mid in mem.inferred:
                out[mid] = max(0.65, mem.inferred[mid])
            elif mid in defaults:
                out[mid] = q_def
            else:
                out[mid] = q_oth

        for mid in known:
            out[mid] = 1.0

        if len(known) >= 4:
            out = {k: (1.0 if k in known else 0.0) for k in out}

        return [(k, v) for k, v in out.items() if v > 0]

    def _build_bench(self, obs):
        out = []
        for s in obs.get("valid_switches", []) or []:
            name = s.get("name")
            if name not in SP:
                continue
            sset = self._set_for(name) or {
                "name": name, "item": SP[name]["item"], "nature": SP[name]["nature"],
                "evs": SP[name]["evs"], "ability": SP[name]["ab"][0], "moves": SP[name]["dm"]
            }
            m = my_mon_from_set(sset, (s.get("hp_percent", 100) or 0) / 100.0)
            if name in self.my_known_stats:
                m.stats = self.my_known_stats[name]
                m.maxhp = m.stats["hp"]
                m.hp = m.maxhp * (s.get("hp_percent", 100) or 0) / 100.0
            out.append((s.get("index"), m))
        return out

    def _update_memory(self, obs):
        foe = obs.get("foe") or {}
        fname = foe.get("name")
        mem = self.foe_mem.setdefault(fname, FoeMemory())
        if self.prev and self.prev["foe_name"] != fname:
            self.foe_switch_turn = obs.get("turn", 0)
            mem.turns_active = 0
        elif self.prev:
            mem.turns_active += 1

        self._ingest_reveals(obs, fname, mem)

        w_raw = str(obs.get("weather") or "").lower()
        if "sand" in w_raw:
            self.weather = "sand"
            self.sand_turns = 5
        elif "rain" in w_raw:
            self.weather = "rain"
            self.sand_turns = 0
        elif "sun" in w_raw:
            self.weather = "sun"
            self.sand_turns = 0
        elif "snow" in w_raw or "hail" in w_raw:
            self.weather = "snow"
            self.sand_turns = 0
        elif w_raw == "none":
            self.weather = ""
            self.sand_turns = 0
        elif fname == "Tyranitar" and (not self.prev or self.prev["foe_name"] != fname):
            self.weather = "sand"
            self.sand_turns = 5
        my = obs.get("my_active") or {}
        if my.get("name") == "Tyranitar" and (not self.prev or self.prev["my_name"] != "Tyranitar"):
            self.weather = "sand"
            self.sand_turns = 5

        if self.prev_action and "knock" in self.prev_action.lower() and self.prev and self.prev["foe_name"] == fname:
            mem.item_known = "none"
            mem.has_no_item = True

        # Infer move from damage
        if self.prev and self.prev["my_name"] == my.get("name") and self.prev["foe_name"] == fname and my.get("name") in SP:
            lost = (self.prev["my_hp"] or 0) - (my.get("hp_percent", 0) or 0)
            if lost >= 3:
                self._infer_from_damage(obs, lost, fname, mem)

    def _ingest_reveals(self, obs, fname, mem):
        foe = obs.get("foe") or {}
        cands = []
        for k in ("moves", "known_moves", "revealed_moves", "moves_seen", "seen_moves", "used_moves"):
            v = foe.get(k)
            if isinstance(v, (list, tuple)):
                cands.extend(v)
        for k in ("last_move", "last_move_used", "last_used_move"):
            if foe.get(k):
                cands.append(foe.get(k))
        for k in ("last_foe_move", "foe_last_move"):
            if obs.get(k):
                cands.append(obs.get(k))
        for ent in cands:
            mid = norm(ent.get("id") or ent.get("name") or ent.get("move")) if isinstance(ent, dict) else norm(ent)
            if mid:
                mem.seen.add(mid)

        ab = foe.get("ability")
        if ab:
            mem.ability_known = norm(ab)
        it = foe.get("item")
        if it:
            mem.item_known = norm(it)

    def _infer_from_damage(self, obs, lost_pct, fname, mem):
        try:
            my = obs.get("my_active") or {}
            sset = self._set_for(my.get("name"))
            if sset is None:
                return
            me = my_mon_from_set(sset, (self.prev["my_hp"] or 100) / 100.0)
            if my.get("name") in self.my_known_stats:
                me.stats = self.my_known_stats[my.get("name")]
                me.maxhp = me.stats["hp"]
                me.hp = me.maxhp * (self.prev["my_hp"] or 100) / 100.0
            f = foe_mon_from_name(fname, (obs.get("foe") or {}).get("hp_percent", 100) / 100.0)
            f.hp = f.maxhp

            matches = []
            for mid in SP[fname]["legal"]:
                mv = MV.get(mid)
                if not mv or mv["c"] == "T" or mv["bp"] == 0 and not mv.get("speedbp"):
                    continue
                rl = damage_rolls(f, me, mid, self.weather)
                lo, hi = rl[0] / me.maxhp * 100, rl[-1] / me.maxhp * 100
                hi_c = hi * 1.5 * 1.1
                if lo * 0.85 - 2 <= lost_pct <= hi_c + 3:
                    matches.append((mid, abs((lo + hi) / 2 - lost_pct)))

            if not matches:
                return
            matches.sort(key=lambda x: x[1])
            dm = set(SP[fname]["dm"])
            dmatch = [m for m in matches if m[0] in dm]
            pool = dmatch if dmatch else matches
            if len(pool) == 1 and len(matches) <= 3:
                mem.seen.add(pool[0][0])
            else:
                for mid, _ in pool[:2]:
                    if mid not in mem.seen:
                        mem.inferred[mid] = max(mem.inferred.get(mid, 0), 0.7 if len(pool) <= 2 else 0.55)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Search Context
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self, agent, obs, me, foe, bench):
        self.agent = agent
        self.obs = obs
        self.me = me
        self.foe = foe
        self.bench = bench
        self.foe_mem = agent.foe_mem.get(foe.name) or FoeMemory()
        w_raw = str(obs.get("weather") or "").lower()
        if "sand" in w_raw:
            self.sand = True
            self.weather = "sand"
        elif "rain" in w_raw:
            self.sand = False
            self.weather = "rain"
        elif "sun" in w_raw:
            self.sand = False
            self.weather = "sun"
        elif "snow" in w_raw or "hail" in w_raw:
            self.sand = False
            self.weather = "snow"
        elif w_raw == "none":
            self.sand = False
            self.weather = ""
        else:
            self.weather = agent.weather
            self.sand = (self.weather == "sand") or (agent.sand_turns > 0)
            if self.sand:
                self.weather = "sand"
        self.foe_first_turn = self.foe_mem.turns_active == 0
        self.P = PARAMS

        self.my_team_hp = {}
        for t in obs.get("my_team", []) or []:
            self.my_team_hp[t.get("name")] = (t.get("hp_percent", 0) or 0) / 100.0
        self.foe_alive_other = self._foe_other_count(obs)
        self.foe_dist = self._foe_distribution()

    def _foe_other_count(self, obs):
        ag = self.agent
        ag.foe_team_hp[self.foe.name] = self.foe.frac
        seen = len(ag.foe_team_hp)
        unseen = max(0, 3 - seen)
        others_hp = sum(v for n, v in ag.foe_team_hp.items() if n != self.foe.name)
        return others_hp + unseen

    def p_faster(self, my_mon, my_boosts_extra=0, foe_boost_extra=0):
        """P(my_mon moves before foe) from speed alone (ties 0.5)."""
        ms = eff_speed(my_mon, self.weather)
        fm = self.foe
        base = SP[fm.name]["b"][5]
        fs_default = fm.stats["spe"]
        mix = [
            (fs_default, 0.62),
            (int(((2 * base + 31 + 63) * LVL // 100 + 5) * 1.1), 0.12),
            (int(((2 * base + 31 + 63) * LVL // 100 + 5) * 1.0), 0.14),
            (int(((2 * base + 31) * LVL // 100 + 5) * 1.0), 0.12)
        ]
        stage = boost_mult(fm.boosts.get("spe", 0) + foe_boost_extra)
        par = 0.5 if fm.status == "par" else 1.0
        p_weather_speed = 0.0
        if self.weather == "sand":
            if any(a == "sandrush" for a, _ in fm.ab_probs):
                p_weather_speed = 1.0 if self.foe_mem.ability_known == "sandrush" else (0.0 if self.foe_mem.ability_known else 0.85)
        elif self.weather == "sun":
            if any(a == "chlorophyll" for a, _ in fm.ab_probs):
                p_weather_speed = 1.0 if self.foe_mem.ability_known == "chlorophyll" else (0.0 if self.foe_mem.ability_known else 0.85)
        elif self.weather == "rain":
            if any(a == "swiftswim" for a, _ in fm.ab_probs):
                p_weather_speed = 1.0 if self.foe_mem.ability_known == "swiftswim" else (0.0 if self.foe_mem.ability_known else 0.85)
        elif self.weather in ("snow", "hail"):
            if any(a == "slushrush" for a, _ in fm.ab_probs):
                p_weather_speed = 1.0 if self.foe_mem.ability_known == "slushrush" else (0.0 if self.foe_mem.ability_known else 0.85)

        mem = self.foe_mem
        if mem.item_known == "choicescarf":
            scarf = 1.0
        elif mem.item_known is not None:
            scarf = 0.0
        else:
            fn_low = fm.name.lower()
            scarf = SPECIES_ITEM_PRIOR.get(fn_low, {}).get("choicescarf", self.P.get("scarf_prob", 0.07))

        total = 0.0
        wsum = 0.0
        weather_options = ((2.0, p_weather_speed), (1.0, 1.0 - p_weather_speed)) if p_weather_speed > 0 else ((1.0, 1.0),)
        for s, w in mix:
            for weathermult, w_p in weather_options:
                for sc_mult, sc_w in ((1.0, 1 - scarf), (1.5, scarf)):
                    es = s * stage * par * weathermult * sc_mult
                    if es < mem.speed_lo * 0.999 or es > mem.speed_hi * 1.001:
                        continue
                    ww = w * sc_w * w_p
                    wsum += ww
                    if ms > es:
                        total += ww
                    elif ms == es:
                        total += ww * 0.5

        if wsum <= 0:
            return 0.5
        return total / wsum

    def _foe_distribution(self):
        """Distribution over foe actions with greedy-priority weighting."""
        foe, me = self.foe, self.me
        scored = []
        for mid, q in foe.moves:
            mv = MV.get(mid)
            if not mv:
                continue
            if mv["c"] == "T":
                u = self._util_value(mid)
                scored.append((u, q, mid, False))
                continue
            rl = damage_rolls(foe, me, mid, self.weather)
            avg = sum(rl) / 16.0 / me.maxhp
            acc = min(1.0, mv["a"] / 100.0)
            v = avg * acc
            if mv.get("sucker"):
                # If we are within Sucker Punch kill range, enemy is VERY likely to click it
                if rl[8] >= me.hp:
                    v += 2.0
                else:
                    v *= 0.9
            if mv.get("first") and not self.foe_first_turn:
                v = 0
            if mv["p"] > 0 and rl[4] >= me.hp:
                v += 2.5
            elif rl[8] >= me.hp:
                v += 0.35
            scored.append((v, q, mid, True))

        scored.sort(key=lambda x: -x[0])
        w = []
        not_better = 1.0
        tot_q = sum(q for _, q, _, _ in scored) or 1.0
        greedy = self.P.get("foe_greedy", 0.72)
        for v, q, mid, atk in scored:
            wi = q * not_better * greedy + (1 - greedy) * q / tot_q
            not_better *= (1 - q)
            w.append([wi, mid, atk])

        s = sum(x[0] for x in w) or 1.0
        # If foe is critically low and facing a bad matchup, switch probability increases
        base_sw = self.P.get("foe_switch", 0.05)
        if foe.frac < 0.25:
            base_sw = self.P.get("foe_switch_low", 0.12)
        ps = base_sw

        out = [((x[0] / s) * (1 - ps), ("atk" if x[2] else "util", x[1])) for x in w if x[0] / s > 0.01]
        out.append((ps, ("switch",)))
        tot = sum(p for p, _ in out)
        return [(p / tot, a) for p, a in out]

    def _util_value(self, mid):
        if mid in SETUP:
            return 0.16
        if mid in HEAL_MOVES:
            return 0.15 if self.foe.frac < 0.55 else 0.0
        if mid in STATUS_MOVES:
            return 0.14 if not self.me.status else 0.0
        if mid == "protect":
            return 0.06
        return 0.02

    def leaf(self, my_mon, my_hp, foe_hp, my_status="", foe_boost=None, intim=0.0, foe_atk_stage=0, my_atk_stage=0, foe_status=""):
        me_frac = max(0.0, my_hp) / my_mon.maxhp
        foe_frac = max(0.0, foe_hp) / self.foe.maxhp

        mat_me = me_frac
        for n, hp in self.my_team_hp.items():
            if n != my_mon.name:
                mat_me += hp
        mat_foe = foe_frac + self.foe_alive_other

        v = (mat_me - mat_foe) * self.P.get("w_mat", 1.0)
        w_race = self.P.get("w_race", 0.25)
        ko_bonus = self.P.get("ko_bonus", 0.20)

        if my_hp <= 0 and foe_hp <= 0:
            return v
        if my_hp <= 0:
            return v - w_race - ko_bonus
        if foe_hp <= 0:
            return v + w_race + ko_bonus

        v += w_race * self._race(my_mon, my_hp, foe_hp, my_status, intim, foe_atk_stage, my_atk_stage, foe_status)
        return v

    def _best_dmg(self, att, dfn, hp_def, intim=0.0, att_status=""):
        best_t = 99.0
        prio_kill = False
        moves_list = att.moves if isinstance(att.moves[0] if att.moves else "", str) else [m for m, _ in att.moves]
        for mid in moves_list:
            mv = MV.get(mid)
            if not mv or mv["c"] == "T":
                continue
            rl = damage_rolls(att, dfn, mid, self.weather)
            d = rl[8]
            if intim and mv["c"] == "P":
                d *= (1 - intim / 3.0)
            if att_status == "brn" and mv["c"] == "P" and att.status != "brn":
                d *= 0.5
            if d <= 0:
                continue
            acc = min(1.0, mv["a"] / 100.0)
            if mv.get("rch"):
                acc *= 0.5
            if mid == "outrage":
                acc *= 0.95
            t = math.ceil(hp_def / d) / max(0.2, acc)
            if mv["p"] > 0 and d >= hp_def:
                prio_kill = True
            if t < best_t:
                best_t = t
        return best_t, prio_kill

    def _race(self, my_mon, my_hp, foe_hp, my_status, intim, foe_atk_stage, my_atk_stage=0, foe_status=""):
        saved_my_b = dict(my_mon.boosts)
        if my_atk_stage:
            my_mon.boosts["atk"] = my_mon.boosts.get("atk", 0) + my_atk_stage
            my_mon.boosts["spa"] = my_mon.boosts.get("spa", 0) + my_atk_stage
        t_me, my_prio = self._best_dmg(my_mon, self.foe, foe_hp, intim, my_status)
        my_mon.boosts = saved_my_b

        foe_cands = [(m, q) for m, q in self.foe.moves if q >= 0.5]
        if not foe_cands:
            foe_cands = self.foe.moves
        tmp_moves = [m for m, _ in foe_cands]
        saved = self.foe.moves
        self.foe.moves = tmp_moves
        saved_b = dict(self.foe.boosts)
        if foe_atk_stage:
            self.foe.boosts["atk"] = self.foe.boosts.get("atk", 0) + foe_atk_stage
            self.foe.boosts["spa"] = self.foe.boosts.get("spa", 0) + foe_atk_stage
        saved_fst = self.foe.status
        if foe_status:
            self.foe.status = foe_status
        t_foe, foe_prio = self._best_dmg(self.foe, my_mon, my_hp)
        self.foe.moves = saved
        self.foe.boosts = saved_b
        self.foe.status = saved_fst

        pf = self.p_faster(my_mon)
        if my_prio and not foe_prio:
            pf = 1.0
        elif foe_prio and not my_prio:
            pf = 0.0
        if my_status == "par":
            pf *= 0.5
        if foe_status == "par" or self.foe.status == "par":
            pf = min(1.0, pf * 1.5)

        t_me = min(t_me, 20)
        t_foe = min(t_foe, 20)
        win_first = 1.0 if t_me <= t_foe else 0.0
        win_second = 1.0 if t_me < t_foe else 0.0
        pw = pf * win_first + (1 - pf) * win_second
        margin = math.tanh((t_foe - t_me) * 0.45)
        return 0.5 * (2 * pw - 1) + 0.5 * margin

    def best_action(self):
        obs = self.obs
        scores = []
        for m in obs.get("valid_moves", []) or []:
            mid = norm(m.get("id") or m.get("name"))
            s = self.eval_move(mid)
            scores.append([s, "move %d" % m.get("index", 1), mid])

        # Desperation Priority Rule:
        # If we are slower than the foe, in lethal danger of being KO'd before acting,
        # and not protected by Focus Sash: prioritize guaranteed chip damage via priority
        # moves rather than clicking a 0-priority move that will never execute because we faint first.
        p_faster = self.p_faster(self.me)
        has_sash = (self.me.item == "focussash" and self.me.hp >= self.me.maxhp - 0.5 and not self.sand)

        if p_faster < 0.5 and not has_sash:
            foe_lethal = False
            foe_max_pri = 0
            for fmid, q in self.foe.moves:
                fmv = MV.get(fmid)
                if fmv and fmv["c"] != "T":
                    rl = damage_rolls(self.foe, self.me, fmid, self.weather)
                    max_dmg = rl[-1]
                    fn_low = self.foe.name.lower()
                    if self.foe_mem.item_known == "lifeorb" or (self.foe_mem.item_known is None and "lifeorb" in SPECIES_ITEM_PRIOR.get(fn_low, {})):
                        max_dmg = max(max_dmg, rl[-1] * 1.3)
                    elif self.foe_mem.item_known == "choiceband" or (self.foe_mem.item_known is None and "choiceband" in SPECIES_ITEM_PRIOR.get(fn_low, {})):
                        if fmv["c"] == "P":
                            max_dmg = max(max_dmg, rl[-1] * 1.5)
                    elif self.foe_mem.item_known == "choicespecs" or (self.foe_mem.item_known is None and "choicespecs" in SPECIES_ITEM_PRIOR.get(fn_low, {})):
                        if fmv["c"] == "S":
                            max_dmg = max(max_dmg, rl[-1] * 1.5)
                    if max_dmg >= self.me.hp or rl[8] >= self.me.hp * 0.88:
                        foe_lethal = True
                        foe_max_pri = max(foe_max_pri, fmv.get("p", 0))

            if foe_lethal:
                best_prio = None
                max_prio_dmg = 0.0
                for m in obs.get("valid_moves", []) or []:
                    mid = norm(m.get("id") or m.get("name"))
                    mv = MV.get(mid)
                    if mv and mv.get("p", 0) > foe_max_pri and mv["c"] != "T":
                        rl = damage_rolls(self.me, self.foe, mid, self.weather)
                        dmg = rl[8]
                        if dmg > max_prio_dmg:
                            max_prio_dmg = dmg
                            best_prio = (m.get("index"), mid, dmg)

                if best_prio is not None and max_prio_dmg > 0:
                    best_prio_mid = best_prio[1]
                    for i, (sc, cmd, mid) in enumerate(scores):
                        if mid == best_prio_mid:
                            scores[i][0] = sc + 1.0
                        else:
                            mv = MV.get(mid)
                            if mv and mv.get("p", 0) <= foe_max_pri:
                                scores[i][0] = sc - 1.0

        sw_scores = []
        for idx, mon in self.bench:
            s = self.eval_switch(mon)
            sw_scores.append((s, "switch %d" % idx, mon.name))

        allsc = scores + sw_scores
        if not allsc:
            return self.agent._fallback(obs)

        best_move = max(scores, key=lambda x: x[0]) if scores else None
        best_sw = max(sw_scores, key=lambda x: x[0]) if sw_scores else None

        if best_move is None:
            return best_sw[1]

        sw_margin = self.P.get("switch_margin", 0.10)
        if len(obs.get("valid_moves", [])) == 1 and self.me.item in ("choiceband", "choicespecs"):
            m_info = obs.get("valid_moves", [])[0]
            mult = m_info.get("type_multiplier", 1.0)
            if mult < 0.9:
                sw_margin = -0.02

        if best_sw is not None and best_sw[0] > best_move[0] + sw_margin:
            return best_sw[1]
        return best_move[1]

    def best_forced_switch(self):
        best = None
        for idx, mon in self.bench:
            intim = self._intim_prob()
            if mon.ability in ("clearbody", "innerfocus"):
                intim = 0.0
            v = self.leaf(mon, mon.hp, self.foe.hp, "", None, intim)
            v += 0.2 * (self.p_faster(mon) - 0.5)
            if best is None or v > best[0]:
                best = (v, idx)
        return "switch %d" % best[1] if best else self.agent._fallback(self.obs)

    def _intim_prob(self):
        return sum(p for a, p in self.foe.ab_probs if a == "intimidate")

    def eval_move(self, mid):
        mv = MV.get(mid)
        if mv is None:
            return -9
        total = 0.0
        worst = 9e9
        for w, fa in self.foe_dist:
            v = self.outcome_move(mid, mv, fa)
            total += w * v
            if w >= self.P.get("worst_w", 0.1):
                worst = min(worst, v)
        if worst > 1e8:
            worst = total

        lam = self.P.get("lam_worst", 0.3)
        score = (1 - lam) * total + lam * worst

        if mv.get("sb"):
            neg = sum(-x for x in mv["sb"].values() if x < 0)
            my_rl = damage_rolls(self.me, self.foe, mid, self.weather)
            if my_rl[8] < self.foe.hp:
                score -= 0.08 * neg
            else:
                score -= 0.02 * neg
        if mid in ("outrage", "petaldance"):
            score -= self.P.get("lock_pen", 0.15)
        return score

    def outcome_move(self, mid, mv, fa):
        me, foe = self.me, self.foe
        my_pri = mv["p"]
        is_status = (mv["c"] == "T")
        my_rl = damage_rolls(me, foe, mid, self.weather) if not is_status else [0.0] * 16
        my_acc = min(1.0, mv["a"] / 100.0)

        kind = fa[0]
        if kind == "switch":
            dmg = sum(my_rl) / 16.0 * 0.55
            frac_dmg = (dmg * my_acc) / max(1.0, foe.maxhp)
            return self.leaf(me, me.hp, foe.maxhp * (1.0 - frac_dmg), "", None, 0.0)

        fmid = fa[1] if len(fa) > 1 else None
        fmv = MV.get(fmid) if fmid else None
        f_rl = [0.0] * 16
        f_pri = 0
        f_acc = 1.0

        if kind == "atk" and fmv:
            f_rl = damage_rolls(foe, me, fmid, self.weather)
            f_pri = fmv["p"]
            f_acc = min(1.0, fmv["a"] / 100.0)
            if fmv.get("first") and not self.foe_first_turn:
                f_rl = [0.0] * 16

        sucker = bool(fmv and fmv.get("sucker"))
        p_first = self.p_faster(me)

        if my_pri > f_pri:
            p_me_first = 1.0
        elif my_pri < f_pri:
            p_me_first = 0.0
        else:
            p_me_first = p_first

        foe_boost_atk = 0
        heal_foe = 0.0
        my_new_status = ""
        protect = (fmid == "protect")
        if kind == "util":
            if fmid in SETUP:
                foe_boost_atk = SETUP[fmid].get("atk", 0) + SETUP[fmid].get("spa", 0)
                foe_boost_atk = min(2, foe_boost_atk)
            if fmid in HEAL_MOVES:
                heal_foe = foe.maxhp * 0.5
            if fmid in STATUS_MOVES:
                st, acc = STATUS_MOVES[fmid]
                if not me.status and st in ("brn", "par", "slp", "psn"):
                    my_new_status = st

        # Model our own status moves
        my_boost_atk = 0
        heal_me = 0.0
        foe_new_status = ""
        my_protect = (mid == "protect")
        if is_status:
            if mid in SETUP:
                my_boost_atk = min(2, SETUP[mid].get("atk", 0) + SETUP[mid].get("spa", 0))
            if mid in HEAL_MOVES:
                heal_me = me.maxhp * 0.5
            if mid in STATUS_MOVES:
                st, acc = STATUS_MOVES[mid]
                if not foe.status and st in ("brn", "par", "slp", "psn"):
                    foe_new_status = st

        recoil = 0.0
        if me.item == "lifeorb" and not is_status:
            recoil += me.maxhp * 0.10

        contact_chip = 0.0
        if mv.get("ct"):
            for ab, pb in foe.ab_probs:
                if ab in ("roughskin", "ironbarbs"):
                    contact_chip += pb * me.maxhp / 8.0
            if self.foe_mem.item_known == "rockyhelmet":
                contact_chip += me.maxhp / 6.0
            elif self.foe_mem.item_known is None:
                rh_p = SPECIES_ITEM_PRIOR.get(foe.name.lower(), {}).get("rockyhelmet", 0.0)
                contact_chip += rh_p * (me.maxhp / 6.0)

        foe_sash_p = 0.0
        if foe.hp >= foe.maxhp - 0.5 and me.ability != "moldbreaker":
            if self.foe_mem.item_known == "focussash":
                foe_sash_p = 1.0
            elif self.foe_mem.item_known is None:
                foe_sash_p = SPECIES_ITEM_PRIOR.get(foe.name.lower(), {}).get("focussash", 0.0)

        my_sash_p = 1.0 if (me.item == "focussash" and me.hp >= me.maxhp - 0.5) else 0.0

        my_samples = roll_samples(my_rl)
        f_samples = roll_samples(f_rl)
        orders = [(p_me_first, True), (1 - p_me_first, False)]
        total = 0.0

        for po, me_first in orders:
            if po <= 1e-9:
                continue
            for dm, pdm in my_samples:
                for hit_m, ph_m in ((1, my_acc), (0, 1 - my_acc)):
                    if ph_m <= 1e-9:
                        continue
                    for df, pdf in f_samples:
                        for hit_f, ph_f in ((1, f_acc), (0, 1 - f_acc)):
                            if ph_f <= 1e-9:
                                continue
                            pr_ = po * pdm * ph_m * pdf * ph_f
                            if pr_ <= 1e-7:
                                continue
                            dmg_m = dm * hit_m if not protect else 0.0
                            dmg_f = df * hit_f if not my_protect else 0.0

                            if me_first:
                                # Player moves first
                                if is_status:
                                    m_hp = min(me.maxhp, me.hp + heal_me)
                                    f_hp = foe.hp
                                    if not sucker and dmg_f > 0:
                                        if my_sash_p > 0 and dmg_f >= m_hp and not (fmv and fmv.get("mh")):
                                            m_hp = 1.0
                                        else:
                                            m_hp = max(0.0, m_hp - dmg_f)
                                    f_hp = min(foe.maxhp, f_hp + heal_foe)
                                    st = my_new_status if (m_hp > 0) else ""
                                    total += pr_ * self.leaf(me, m_hp, f_hp, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                                else:
                                    # Attack move
                                    if dmg_m >= foe.hp and not mv.get("mh"):
                                        # Lethal hit!
                                        # Subcase A: Foe survives via Focus Sash (prob foe_sash_p)
                                        if foe_sash_p > 0:
                                            f_hp_s = 1.0
                                            m_hp_s = me.hp
                                            if hit_m and mv.get("ct"):
                                                m_hp_s -= contact_chip
                                            if not sucker and dmg_f > 0:
                                                if my_sash_p > 0 and dmg_f >= m_hp_s and not (fmv and fmv.get("mh")):
                                                    m_hp_s = 1.0
                                                else:
                                                    m_hp_s = max(0.0, m_hp_s - dmg_f)
                                            f_hp_s = min(foe.maxhp, f_hp_s + heal_foe)
                                            if m_hp_s > 0 and hit_m:
                                                m_hp_s = max(0.0, m_hp_s - recoil)
                                            st = my_new_status if (m_hp_s > 0) else ""
                                            v_sash = self.leaf(me, m_hp_s, f_hp_s, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                                        else:
                                            v_sash = 0.0

                                        # Subcase B: Foe does not have Sash -> Faints, 0 retaliation!
                                        f_hp_no = 0.0
                                        m_hp_no = me.hp
                                        if hit_m and mv.get("ct"):
                                            m_hp_no -= contact_chip
                                        if m_hp_no > 0 and hit_m:
                                            m_hp_no = max(0.0, m_hp_no - recoil)
                                        v_no = self.leaf(me, m_hp_no, f_hp_no, me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)

                                        total += pr_ * (foe_sash_p * v_sash + (1.0 - foe_sash_p) * v_no)
                                    else:
                                        # Non-lethal attack
                                        f_hp = max(0.0, foe.hp - dmg_m)
                                        m_hp = me.hp
                                        if hit_m and mv.get("ct"):
                                            m_hp -= contact_chip
                                        if f_hp > 0:
                                            if not sucker and dmg_f > 0:
                                                if my_sash_p > 0 and dmg_f >= m_hp and not (fmv and fmv.get("mh")):
                                                    m_hp = 1.0
                                                else:
                                                    m_hp = max(0.0, m_hp - dmg_f)
                                            f_hp = min(foe.maxhp, f_hp + heal_foe)
                                        if m_hp > 0 and hit_m:
                                            m_hp = max(0.0, m_hp - recoil)
                                        m_hp = max(0.0, m_hp)
                                        st = my_new_status if (m_hp > 0) else ""
                                        total += pr_ * self.leaf(me, m_hp, f_hp, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                            else:
                                # Foe moves first
                                if sucker and is_status:
                                    dmg_f = 0.0

                                m_hp = me.hp
                                if dmg_f > 0:
                                    if my_sash_p > 0 and dmg_f >= m_hp and not (fmv and fmv.get("mh")):
                                        m_hp = 1.0
                                    else:
                                        m_hp = max(0.0, m_hp - dmg_f)

                                if m_hp > 0:
                                    # Player survives and retaliates
                                    if is_status:
                                        m_hp = min(me.maxhp, m_hp + heal_me)
                                        f_hp = min(foe.maxhp, foe.hp + heal_foe)
                                        st = my_new_status if (m_hp > 0) else ""
                                        total += pr_ * self.leaf(me, m_hp, f_hp, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                                    else:
                                        if dmg_m >= foe.hp and not mv.get("mh"):
                                            # Lethal retaliation at end of turn
                                            if foe_sash_p > 0:
                                                m_hp_s = m_hp - (contact_chip if (hit_m and mv.get("ct")) else 0)
                                                if m_hp_s > 0 and hit_m:
                                                    m_hp_s = max(0.0, m_hp_s - recoil)
                                                st = my_new_status if (m_hp_s > 0) else ""
                                                v_sash = self.leaf(me, m_hp_s, 1.0, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                                            else:
                                                v_sash = 0.0

                                            m_hp_no = m_hp - (contact_chip if (hit_m and mv.get("ct")) else 0)
                                            if m_hp_no > 0 and hit_m:
                                                m_hp_no = max(0.0, m_hp_no - recoil)
                                            v_no = self.leaf(me, m_hp_no, 0.0, me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)

                                            total += pr_ * (foe_sash_p * v_sash + (1.0 - foe_sash_p) * v_no)
                                        else:
                                            f_hp = max(0.0, foe.hp - dmg_m)
                                            if hit_m and mv.get("ct"):
                                                m_hp -= contact_chip
                                            if m_hp > 0 and hit_m:
                                                m_hp = max(0.0, m_hp - recoil)
                                            m_hp = max(0.0, m_hp)
                                            f_hp = min(foe.maxhp, f_hp + heal_foe) if f_hp > 0 else 0.0
                                            st = my_new_status if (m_hp > 0) else ""
                                            total += pr_ * self.leaf(me, m_hp, f_hp, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                                else:
                                    # Player fainted before acting
                                    f_hp = min(foe.maxhp, foe.hp + heal_foe)
                                    total += pr_ * self.leaf(me, 0.0, f_hp, "", None, 0.0, foe_boost_atk, 0, "")
        return total

    def eval_switch(self, mon):
        foe = self.foe
        intim_p = self._intim_prob()
        if mon.ability in ("clearbody", "innerfocus", "oblivious", "owntempo", "scrappy"):
            intim_p = 0.0
        total = 0.0
        worst = 9e9
        for w, fa in self.foe_dist:
            kind = fa[0]
            fmid = fa[1] if len(fa) > 1 else None
            fmv = MV.get(fmid) if fmid else None
            if kind == "atk" and fmv:
                rl = damage_rolls(foe, mon, fmid, self.weather)
                acc = min(1.0, fmv["a"] / 100.0)
                if fmv.get("first") and not self.foe_first_turn:
                    rl = [0.0] * 16
                # Sucker punch fails if target is switching!
                if fmv.get("sucker"):
                    rl = [0.0] * 16
                v = 0.0
                for d, pd in roll_samples(rl):
                    for hit, ph in ((1, acc), (0, 1 - acc)):
                        if ph <= 1e-9:
                            continue
                        hp = max(0.0, mon.hp - d * hit)
                        if hp > 0 and d > 0:
                            best_t, prio_k = self._best_dmg(mon, foe, foe.hp, intim_p)
                            if best_t > 1.0 and hp <= d:
                                v += pd * ph * (self.leaf(mon, 0.0, foe.hp, "", None, intim_p) - 0.25)
                                continue
                        v += pd * ph * self.leaf(mon, hp, foe.hp, "", None, intim_p)
            elif kind == "util":
                foe_boost = 0
                if fmid in SETUP:
                    foe_boost = min(2, SETUP[fmid].get("atk", 0) + SETUP[fmid].get("spa", 0))
                v = self.leaf(mon, mon.hp, min(foe.maxhp, foe.hp + (foe.maxhp * 0.5 if fmid in HEAL_MOVES else 0)), "", None, intim_p, foe_boost)
            else:
                v = self.leaf(mon, mon.hp, foe.hp, "", None, intim_p)

            total += w * v
            if w >= self.P.get("worst_w", 0.1):
                worst = min(worst, v)

        if worst > 1e8:
            worst = total
        lam = self.P.get("lam_worst", 0.3)
        score = (1 - lam) * total + lam * worst

        score -= self.P.get("switch_cost", 0.03)
        if self.agent.prev_action and "switch" in self.agent.prev_action:
            score -= 0.25
        if self.me.status in ("slp", "frz"):
            score += 0.15
        return score
