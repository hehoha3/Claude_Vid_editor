# Africa AI species folders (user 2026-10-22): D:\AI_video\_africa\<species>, new generated clips go to _africa\_check.
# Folder names = the names organize.py --africa files the tagged clips into (scan_source AFRICA_FOLDERS + ALIAS_AFRICA).
# Safe to re-run: existing folders and their files are left as they are.
$root = 'D:\AI_video\_africa'
$names = @(
  # predators
  'lion', 'leopard', 'cheetah', 'wild_dog', 'hyena', 'jackal', 'serval', 'caracal', 'honey_badger', 'mongoose', 'meerkat',
  # big herbivores + primates
  'buffalo', 'wildebeest', 'zebra', 'rhino', 'hippo', 'elephant', 'giraffe', 'warthog', 'baboon',
  # antelopes (other small antelopes -> antelope)
  'impala', 'red_lechwe', 'springbok', 'gazelle', 'kudu', 'nyala', 'eland', 'blesbok', 'topi', 'hartebeest', 'oryx', 'antelope',
  # reptiles, birds, small things
  'crocodile', 'snake', 'ostrich', 'vulture', 'eagle', 'marabou_stork', 'secretary_bird', 'bird', 'insects',
  # scenery (organize: landscape\<setting tag>)
  'landscape\savanna', 'landscape\grassland', 'landscape\swamp', 'landscape\river', 'landscape\waterhole',
  'landscape\lake', 'landscape\mountain', 'landscape\sky'
)
foreach ($n in $names) { New-Item -ItemType Directory -Path (Join-Path $root $n) -Force | Out-Null }
Write-Host "$((Get-ChildItem $root -Directory -Recurse).Count) folders under $root"
