# ------------------------------------------- . ----------------------------------------
# Filename : oscilloscope.py                  | Cree (Launch Mode = Manual) une Compo   |
#                                              | "Oscilloscope" : point lumineux qui      |
#                                              | balaie l'ecran de gauche a droite en     |
#                                              | boucle, oscille en Y selon une bande de  |
#                                              | frequence audio (Voicemeeter), et laisse |
#                                              | une trace phosphorescente (vert CRT).    |
#                                              |                                          |
#                                              | STRUCTURE :                              |
#                                              | Oscilloscope (Compo master)               |
#                                              |  - Trace (Compo)                         |
#                                              |     - Traceur (Compo) : Trace Line       |
#                                              |       (1920 pts) + Point (cercle) +      |
#                                              |       Trace Writer (script At Every      |
#                                              |       Update qui "peint" la ligne) +     |
#                                              |       Mask (Placement Mask suiveur,      |
#                                              |       feather gauche = echo/fade)        |
#                                              |     - Links : Y Audio (spectre)          |
#                                              |     - Animations : X Sweep (boucle)      |
#                                              |     - Modifiers : 10 Echos (FrameDelay), |
#                                              |       Colorize (vert phosphore),         |
#                                              |       Gaussian Blur, 2D Transform (+     |
#                                              |       Circle Mask), Mask (Circle Mask    |
#                                              |       = ecran CRT)                       |
#                                              |  - Screen (Compo) : backscreen (degrade  |
#                                              |    radial vert) + "100 Px Grid" (Test    |
#                                              |    Pattern, seul le composant grid       |
#                                              |    actif, fond transparent, actif)       |
#                                              |  - Screen Masque (Compo) : Masque        |
#                                              |    (UniformTextureGenerator noir avec    |
#                                              |    masque bezier 8 points = silhouette   |
#                                              |    ecran)                                |
#                                              |  - Parameters : Frequency/Amplitude       |
#                                              |    Min/Max, Trace Position Y, parametre  |
#                                              |    combine (saturation+2 blurs, anime    |
#                                              |    par le flicker via 3 courbes          |
#                                              |    KeyframeFunction independantes)       |
#                                              |  - Animations : Screen Flickering+Blur   |
#                                              |    (Noise simplex, anime le parametre    |
#                                              |    combine)                              |
#                                              |  - Links : Circle Mask Compensation (3   |
#                                              |    liens qui compensent le deplacement   |
#                                              |    de Trace Position Y sur les 3 masques |
#                                              |    circulaires/suiveur imbriques dans    |
#                                              |    Trace, pour qu'ils restent fixes a    |
#                                              |    l'ecran)                              |
#                                              |                                          |
#                                              | GOTCHAS IMPORTANTS :                     |
#                                              | - Toute forme cercle neuve (point,       |
#                                              |   masques circulaires) repasse a 500 px  |
#                                              |   1-2 images APRES la fin du script ->   |
#                                              |   le Trace Writer reecrit les tailles    |
#                                              |   pendant ses 30 premieres images.       |
#                                              | - Audio : bande en Hz, niveaux en dB     |
#                                              |   (pas en %) ; chaque borne est limitee  |
#                                              |   par l'autre (debut, fin, puis debut).  |
#                                              | - Size2d/ScaleFactor ont un flag         |
#                                              |   `.linked` (True par defaut) qui force  |
#                                              |   width=height des qu'on en modifie un   |
#                                              |   -> toujours `.linked.set(False)` AVANT |
#                                              |   de regler width/height separement.     |
#                                              | - CustomEnumeration ne se peuple pas     |
#                                              |   dans la declaration -> peuplage dans   |
#                                              |   le corps, protege par un if.           |
#                                              | - ParametricScalarFunction : TOUJOURS    |
#                                              |   regler minimum/maximum/wrapMode         |
#                                              |   explicitement (defauts pas fiables,    |
#                                              |   sinon sortie constante/plate).          |
#                                              | - Pour un mapping/inversion de valeur    |
#                                              |   via un Link, utiliser un               |
#                                              |   FunctionLinkModifier + KeyframeFunction|
#                                              |   (input=Percentage,output=Percentage)   |
#                                              |   avec 2 keyframes - plus fiable qu'un   |
#                                              |   Multiply/Offset modifier pour ce cas.  |
# Started  : 2026-07-08                        |                                        |
# ------------------------------------------- . ----------------------------------------

# =============== OPTIONS (visibles/modifiables dans le panneau du Script) ===============
nPoints: Oil.PositiveInteger(1920)          # nombre de points de la ligne de trace (largeur px de la compo)
sweepPeriod: Oil.PositiveReal(4.0)          # secondes pour balayer l'ecran une fois
nEchoes: Oil.PositiveInteger(10)            # nombre d'echos FrameDelay pour combler les trous a haute vitesse
oscLabel: Oil.String("Oscilloscope")        # nom du calque cree dans la scene
freqMinHz: Oil.PositiveReal(40.0)           # bas de la bande audio suivie (Hz)
freqMaxHz: Oil.PositiveReal(250.0)          # haut de la bande audio suivie (Hz)
levelMinDb: Oil.Real(-50.0)                 # niveau (dB) qui met le point en bas
levelMaxDb: Oil.Real(0.0)                   # niveau (dB) qui met le point en haut
pointSize: Oil.PositiveReal(20.0)           # diametre du point lumineux (px)
# ==========================================================================================

N_POINTS = script.nPoints.get()
SWEEP_PERIOD = script.sweepPeriod.get()
N_ECHOES = script.nEchoes.get()
OSC_LABEL = script.oscLabel.get()
# The spectrum extractor works in Hz and dB (not in percentages).
FREQ_MIN = max(22.05, script.freqMinHz.get())
FREQ_MAX = max(FREQ_MIN + 1.0, script.freqMaxHz.get())
LEVEL_MIN = min(script.levelMinDb.get(), script.levelMaxDb.get() - 1.0)
LEVEL_MAX = min(0.0, script.levelMaxDb.get())
POINT_PX = max(2.0, script.pointSize.get())

WRAP_MODE_REPEAT = 1
BLENDING_MODE_LINEAR_DODGE = 12
LAUNCH_MODE_RESTART_WITH_ACTIVATION = 1
FEATHER_LINK_NONE = 0
MASK_BLENDING_ADD = 0
PATH_INTERP = {"linear": 0, "quadratic": 1, "cubic": 2}


def makeKeyframeCurve(keyframes_data):
    """Cree un FunctionLinkModifier(Percentage->Percentage) avec une KeyframeFunction.
    Plus fiable qu'un Multiply/Offset modifier pour un mapping/inversion de valeur."""
    func = Oil.createObject("KeyframeFunction({input = Percentage, output = Percentage})")
    for kdata in keyframes_data:
        kf = Oil.createObject("Keyframe({input = Percentage, output = Percentage})")
        kf.position.set(kdata["position"])
        kf.key.set(kdata["key"])
        kf.inputInterpolator = Oil.createObject("LinearKeyframeInterpolator")
        kf.outputInterpolator = Oil.createObject("LinearKeyframeInterpolator")
        func.keyframes.append(kf)
    mod = Oil.createObject("FunctionLinkModifier({input = Percentage, output = Percentage})")
    mod.function = func
    return mod


# --- Supprime l'ancienne version ---
oldLayer = None
for l in script.parentElement.layers:
    if l.getFriendlyName() == OSC_LABEL:
        oldLayer = l
        break
if oldLayer is not None:
    script.parentElement.layers.remove(oldLayer)

# ============================================================================
# TRACEUR : ligne (1920 pts) + point + writer + masque suiveur
# ============================================================================
pointShape = Oil.createObject("ShapeLayer")
pointShape.label = "Oscilloscope Point"
circleGen = Oil.createObject("CircleShapeGenerator")
pointShape.generator = circleGen
# A small bright dot (SMODE gives a new circle 500 px: its size is written again by the Trace Writer).
pointShape.renderer.fill.enabled = True
pointShape.renderer.fill.color.red.set(0.02848031371831894)
pointShape.renderer.fill.color.green.set(0.976307213306427)
pointShape.renderer.fill.color.blue.set(0.0)
pointShape.renderer.fill.color.alpha.set(1.0)
pointShape.renderer.stroke.enabled = False
pointShape.renderer.placement.position.x = 0.5
pointShape.renderer.placement.position.y = 0.5

lineShape = Oil.createObject("ShapeLayer")
lineShape.label = "Trace Line"
linePathGen = Oil.createObject("PathShapeGenerator")
for i in range(N_POINTS):
    cp = Oil.createObject("Path2dControlPoint")
    cp.position.x = i / (N_POINTS - 1)
    cp.position.y = 0.5
    linePathGen.path.points.append(cp)
lineShape.generator = linePathGen
lineShape.renderer.fill.enabled = False
lineShape.renderer.stroke.enabled = True
lineShape.renderer.stroke.thickness.set(8.0)

traceurCompo = Oil.createObject("Compo")
traceurCompo.layers.append(lineShape)
traceurCompo.layers.append(pointShape)

# Script "At Every Update" qui peint la ligne : lit position du point mobile,
# interpole entre l'ancien et le nouvel index pour ne jamais laisser de trous.
writerSourceCode = '''
lastIdx: Oil.Integer(-1)
lastY: Oil.Real(0.5)
sizeFrames: Oil.Integer(0)   # internal: frames since the sizes were written

# SMODE puts every new circle back to 500 px a frame or two after it is installed: during its first frames, this
# script writes the sizes again (point, the two circle masks of Trace, the circle mask of the grid).
SIZE_FIX_FRAMES = 30
if script.sizeFrames.get() < SIZE_FIX_FRAMES:
    script.sizeFrames.set(script.sizeFrames.get() + 1)

    def setSize(gen, w, h):
        if gen is None:
            return
        size = gen.placement.scale.size
        size.linked.set(False)
        size.width.set(w)
        size.height.set(h)

    def firstCircle(modifier):
        for mk in modifier.masks:
            if mk.getOilClassName() == "ShapeTextureMask" and mk.shape is not None:
                return mk.shape
        return None

    traceurCompo = script.parentElement
    for l in traceurCompo.layers:
        if l.getFriendlyName() == "Oscilloscope Point":
            setSize(l.generator, POINT_W, POINT_H)
    traceCompo = traceurCompo.parentElement.parentElement      # Traceur layer -> Trace compo
    for m in traceCompo.modifiers:
        if m.getFriendlyName() == "2D Transform":
            setSize(firstCircle(m), 1.0385, 1.463)
        elif m.getFriendlyName() == "Mask":
            setSize(firstCircle(m), 0.9, 2.0)
    mainCompo = traceCompo.parentElement.parentElement          # Trace layer -> Oscilloscope compo
    for l in mainCompo.layers:
        if l.getFriendlyName() == "Screen":
            for g in l.generator.layers:
                if g.generator is not None and g.generator.getOilClassName() == "TestPatternTextureGenerator":
                    for m in g.generator.modifiers:
                        if m.getFriendlyName() == "2D Transform":
                            setSize(firstCircle(m), 1.0385, 1.463)

movingShape = None
lineShape = None
for l in script.parentElement.layers:
    if l.getOilClassName() == "ShapeLayer":
        if l.getFriendlyName() == "Trace Line":
            lineShape = l
        elif l.getFriendlyName() == "Oscilloscope Point":
            movingShape = l
if movingShape is None or lineShape is None:
    raise RuntimeError("Trace Line or Oscilloscope Point missing in Traceur: run the Oscilloscope script again")

px = movingShape.renderer.placement.position.x.get()
py = movingShape.renderer.placement.position.y.get()

points = lineShape.generator.path.points
n = len(points)
idx = max(0, min(n - 1, int(round(px * (n - 1)))))

prevIdx = script.lastIdx.get()
prevY = script.lastY.get()

if prevIdx < 0 or abs(idx - prevIdx) > n // 2:
    points[idx].position.y.set(py)
else:
    step = 1 if idx >= prevIdx else -1
    span = abs(idx - prevIdx)
    for i in range(span + 1):
        t = i / span if span > 0 else 1.0
        y = prevY + (py - prevY) * t
        points[prevIdx + i * step].position.y.set(y)

script.lastIdx.set(idx)
script.lastY.set(py)
'''
writerSourceCode = writerSourceCode.replace("POINT_W", repr(POINT_PX / 1920.0)).replace("POINT_H", repr(POINT_PX / 1080.0))
writerScript = Oil.createObject("PythonScriptTool")
writerScript.label = "Trace Writer"
writerScript.script.sourceCode.set(writerSourceCode)
writerScript.launchMode.set(4)  # atEveryUpdate
traceurCompo.tools.append(writerScript)

# Masque suiveur (Placement Mask) : feather gauche = fondu progressif derriere le point
travelMask = Oil.createObject("PlacementTextureMask")
travelMask.resolution.width.set(1920)
travelMask.resolution.height.set(1080)
travelMask.inverse.set(False)
travelMask.opacity.set(1.0)
travelMask.feather.link.set(FEATHER_LINK_NONE)
travelMask.feather.left.set(0.606)
travelMask.feather.right.set(0.0)
travelMask.feather.top.set(0.0)
travelMask.feather.bottom.set(0.0)
travelMask.placement.anchor.x = 0.975
travelMask.placement.anchor.y = 0.5
travelMask.placement.position.x = 0.005
travelMask.placement.position.y = 0.5
travelMask.placement.scale.scaleFactor.linked.set(False)
travelMask.placement.scale.scaleFactor.width.set(0.34)
travelMask.placement.scale.scaleFactor.height.set(1.0)

traceurMaskMod = Oil.createObject("MaskTextureModifier")
traceurMaskMod.label = "Mask"
traceurMaskMod.masks.append(travelMask)
traceurCompo.modifiers.append(traceurMaskMod)

traceurLayer = Oil.createObject("TextureLayer")
traceurLayer.generator = traceurCompo
traceurLayer.label = "Traceur"
traceurLayer.renderer.placement.position.x = 0.5
traceurLayer.renderer.placement.position.y = 0.584

# ============================================================================
# TRACE : Traceur + audio Y + sweep X + echos + colorize + blur + transform + masque CRT
# ============================================================================
traceCompo = Oil.createObject("Compo")
traceCompo.layers.append(traceurLayer)

# Audio input: the first audio device with input channels (a DirectSound one first), its "Left" channel
# (else its first one).
audioDevices = [d for d in engine.devices.devices
                if d.getOilClassName() == "JuceAudioDevice" and len(d.inputChannels) > 0]
audioDevices.sort(key=lambda d: 0 if "DirectSound" in str(d.identifier) else 1)
if not audioDevices:
    raise RuntimeError("No audio input device in SMODE (Devices panel): add one, then run the script again")
dsDevice = audioDevices[0]
audioChannel = dsDevice.inputChannels[0]
for ch in dsDevice.inputChannels:
    if ch.getFriendlyName() == "Left":
        audioChannel = ch
        break

ySource = Oil.createObject("AudioSpectrumLinkSource")
ySource.extractor.audioChannel.set(audioChannel)
# Each bound is clamped by the other one: begin, end, then begin again works for any band.
ySource.extractor.frequencyInterval.begin.set(FREQ_MIN)
ySource.extractor.frequencyInterval.end.set(FREQ_MAX)
ySource.extractor.frequencyInterval.begin.set(FREQ_MIN)
ySource.extractor.amplitudeInterval.begin.set(LEVEL_MIN)
ySource.extractor.amplitudeInterval.end.set(LEVEL_MAX)
ySource.extractor.amplitudeInterval.begin.set(LEVEL_MIN)

ySmooth = Oil.createObject("SmoothLinkModifier")
ySmooth.positiveSpeed.set(20.0)
ySmooth.negativeSpeed.set(5.0)

yTarget = Oil.createObject("ParameterLinkTarget")
yTarget.target.set(pointShape.renderer.placement.position.y)
yTarget.modifiers.append(ySmooth)

yLink = Oil.createObject("Link")
yLink.label = "Y Audio"
yLink.source = ySource
yLink.targets.append(yTarget)

traceLinkBank = Oil.createObject("LinkBank")
traceLinkBank.label = "Links"
traceLinkBank.links.append(yLink)
traceCompo.tools.append(traceLinkBank)

xCue = Oil.createObject("FunctionCue(Percentage)")
xCue.label = "X Sweep"
xShape = Oil.createObject("LinearRampFunctionShape")
xFunction = Oil.createObject("ParametricScalarFunction({input = Seconds, output = Percentage})")
xFunction.shape = xShape
xFunction.parameters.maximum = 1.0
xFunction.parameters.period = SWEEP_PERIOD
xFunction.parameters.wrapMode.set(WRAP_MODE_REPEAT)
xCue.function = xFunction
xCue.parameters.looping = True
xCue.parameters.launchMode.set(LAUNCH_MODE_RESTART_WITH_ACTIVATION)
xCue.transport.length = SWEEP_PERIOD

xTarget1 = Oil.createObject("ParameterLinkTarget")
xTarget1.target.set(pointShape.renderer.placement.position.x)
xCue.targets.append(xTarget1)

xTarget2 = Oil.createObject("ParameterLinkTarget")
xTarget2.target.set(travelMask.placement.position.x)
xCue.targets.append(xTarget2)

traceAnimBank = Oil.createObject("AnimationBank")
traceAnimBank.label = "Animations"
traceAnimBank.animations.append(xCue)
traceCompo.tools.append(traceAnimBank)
xCue.transport.play.trig()

for i in range(1, N_ECHOES + 1):
    delayMod = Oil.createObject("FrameDelayTextureModifier")
    delayMod.label = f"Echo {i}"
    delayMod.frames.set(i)
    delayMod.blendingMode.set(BLENDING_MODE_LINEAR_DODGE)
    delayMod.intensity.set(max(0.05, 1.0 - (i / N_ECHOES)))
    traceCompo.modifiers.append(delayMod)

colorizeMod = Oil.createObject("ColorizeTextureModifier")
colorizeMod.label = "Colorize"
colorizeMod.intensity.set(1.0)
tritone = Oil.createObject("TritoneColorFunction")
tritone.beginColor.red.set(0.0)
tritone.beginColor.green.set(0.0)
tritone.beginColor.blue.set(0.0)
tritone.beginColor.alpha.set(1.0)
tritone.intermediateColor.red.set(0.2805473804473877)
tritone.intermediateColor.green.set(0.5610947608947754)
tritone.intermediateColor.blue.set(0.0)
tritone.intermediateColor.alpha.set(1.0)
tritone.intermediatePosition.set(0.5)
tritone.endColor.red.set(0.7506299018859863)
tritone.endColor.green.set(1.0)
tritone.endColor.blue.set(0.0)
tritone.endColor.alpha.set(1.0)
colorizeMod.gradient = tritone
traceCompo.modifiers.append(colorizeMod)

traceBlur = Oil.createObject("BlurV8TextureModifier")
traceBlur.label = "Gaussian Blur"
traceBlur.intensity.set(0.914892831566786)
traceBlur.radius.set(14.0)
traceCompo.modifiers.append(traceBlur)

traceTransform = Oil.createObject("Transform2dTextureModifier")
traceTransform.label = "2D Transform"
traceTransform.intensity.set(1.0)
traceTransform.frame.position.x = 0.5
traceTransform.frame.position.y = 0.5
traceTransform.frame.rotation.set(0.0)
traceTransform.frame.scale.scaleFactor.width.set(1.3369999999999693)
traceTransform.frame.scale.scaleFactor.height.set(1.3369999999999693)
traceCompo.modifiers.append(traceTransform)

# Circle Mask du 2D Transform (valeurs de scale reappliquees en fin de script, voir POST-INSERTION FIXES)
transformCircleGen = Oil.createObject("CircleShapeGenerator")
transformCircleGen.placement.anchor.x = 0.5
transformCircleGen.placement.anchor.y = 0.5
transformCircleGen.placement.position.x = 0.5
transformCircleGen.placement.position.y = 0.5
transformCircleGen.placement.rotation.set(0.0)
transformCircleGen.placement.scale.size.linked.set(False)
transformCircleGen.placement.scale.size.width.set(1.0385)
transformCircleGen.placement.scale.size.height.set(1.463)

transformCircleMask = Oil.createObject("ShapeTextureMask")
transformCircleMask.label = "Circle Mask"
transformCircleMask.resolution.width.set(1920)
transformCircleMask.resolution.height.set(1080)
transformCircleMask.blendingMode.set(MASK_BLENDING_ADD)
transformCircleMask.opacity.set(1.0)
transformCircleMask.inverse.set(False)
transformCircleMask.feather.enabled.set(True)
transformCircleMask.feather.width.set(548.0)
transformCircleMask.shape = transformCircleGen
traceTransform.masks.append(transformCircleMask)

# Masque circulaire = ecran CRT (valeurs de scale reappliquees en fin de script)
crtCircleGen = Oil.createObject("CircleShapeGenerator")
crtCircleGen.placement.position.x = 0.5
crtCircleGen.placement.position.y = 0.5
crtCircleGen.placement.scale.size.linked.set(False)
crtCircleGen.placement.scale.size.width.set(0.9)
crtCircleGen.placement.scale.size.height.set(2.0)

crtShapeMask = Oil.createObject("ShapeTextureMask")
crtShapeMask.resolution.width.set(1920)
crtShapeMask.resolution.height.set(1080)
crtShapeMask.inverse.set(False)
crtShapeMask.feather.enabled.set(True)
crtShapeMask.feather.width.set(158.5)
crtShapeMask.shape = crtCircleGen

traceShapeMaskMod = Oil.createObject("MaskTextureModifier")
traceShapeMaskMod.label = "Mask"
traceShapeMaskMod.masks.append(crtShapeMask)
traceCompo.modifiers.append(traceShapeMaskMod)

traceLayer = Oil.createObject("TextureLayer")
traceLayer.generator = traceCompo
traceLayer.label = "Trace"

# ============================================================================
# SCREEN : backscreen (degrade radial) + "100 Px Grid" (Test Pattern, grid seul actif)
# ============================================================================
backscreenLayer = Oil.createObject("TextureLayer")
backscreenLayer.label = "backscreen"
bgGen = Oil.createObject("GradientTextureGenerator")
bgGen.type = Oil.createObject("Circular2dGradient")
bgGen.smoothness.set(0.96)
bgGen.resolution.width.set(1920)
bgGen.resolution.height.set(1080)
bgGradient = Oil.createObject("BitoneColorFunction")
bgGradient.beginColor.red.set(0.46326324343681335)
bgGradient.beginColor.green.set(0.9761388301849365)
bgGradient.beginColor.blue.set(0.4388781785964966)
bgGradient.beginColor.alpha.set(1.0)
bgGradient.endColor.red.set(0.2090066373348236)
bgGradient.endColor.green.set(0.6980850100517273)
bgGradient.endColor.blue.set(0.16031265258789062)
bgGradient.endColor.alpha.set(1.0)
bgGen.gradient = bgGradient
bgGen.position.center.x = 0.5
bgGen.position.center.y = 0.5
bgGen.position.size.width.set(1887.46484375)
bgGen.position.size.height.set(1316.3465576171875)
backscreenLayer.generator = bgGen

gridLayer = Oil.createObject("TextureLayer")
gridGen = Oil.createObject("TestPatternTextureGenerator")
gridGen.preset.libraryName.set("Default")
gridGen.preset.presetName.set("100 Px Grid")
gridGen.resolution.width.set(1920)
gridGen.resolution.height.set(1080)
gridGen.background.alpha.set(0.0)  # fond transparent

for comp_name in ("horizontalBar", "verticalBar", "diagonals", "corners", "cornerCircles",
                  "centeredCircles", "edges", "logo", "coloredCheckerBoard", "resolutionText",
                  "tileLabels", "labelText"):
    getattr(gridGen, comp_name).enabled.set(False)

gridGen.grid.enabled.set(True)
gridGen.grid.color.red.set(0.3913455009460449)
gridGen.grid.color.green.set(0.6260162591934204)
gridGen.grid.color.blue.set(0.3104633390903473)
gridGen.grid.color.alpha.set(1.0)
gridGen.grid.thickness.set(2.1499999999999995)

gridTransformMod = Oil.createObject("Transform2dTextureModifier")
gridTransformMod.label = "2D Transform"
gridTransformMod.frame.scale.scaleFactor.width.set(1.0649999999999942)
gridTransformMod.frame.scale.scaleFactor.height.set(1.0649999999999942)

gridTransformCircleGen = Oil.createObject("CircleShapeGenerator")
gridTransformCircleGen.placement.anchor.x = 0.5
gridTransformCircleGen.placement.anchor.y = 0.5
gridTransformCircleGen.placement.position.x = 0.5
gridTransformCircleGen.placement.position.y = 0.5
gridTransformCircleGen.placement.rotation.set(0.0)
gridTransformCircleGen.placement.scale.size.linked.set(False)
gridTransformCircleGen.placement.scale.size.width.set(1.0385)
gridTransformCircleGen.placement.scale.size.height.set(1.463)

gridTransformCircleMask = Oil.createObject("ShapeTextureMask")
gridTransformCircleMask.label = "Circle Mask"
gridTransformCircleMask.resolution.width.set(1920)
gridTransformCircleMask.resolution.height.set(1080)
gridTransformCircleMask.blendingMode.set(MASK_BLENDING_ADD)
gridTransformCircleMask.opacity.set(1.0)
gridTransformCircleMask.inverse.set(False)
gridTransformCircleMask.feather.enabled.set(True)
gridTransformCircleMask.feather.width.set(548.0)
gridTransformCircleMask.shape = gridTransformCircleGen
gridTransformMod.masks.append(gridTransformCircleMask)
gridGen.modifiers.append(gridTransformMod)

gridBlurMod = Oil.createObject("BlurV8TextureModifier")
gridBlurMod.label = "Gaussian Blur"
gridBlurMod.intensity.set(0.9541838035733737)
gridBlurMod.radius.set(5.0)
gridGen.modifiers.append(gridBlurMod)

gridLayer.generator = gridGen
gridLayer.activation.set(1)  # actif

screenCompo = Oil.createObject("Compo")
screenCompo.layers.append(backscreenLayer)
screenCompo.layers.append(gridLayer)

screenLayer = Oil.createObject("TextureLayer")
screenLayer.generator = screenCompo
screenLayer.label = "Screen"
screenLayer.renderer.blendingMode.set(BLENDING_MODE_LINEAR_DODGE)

# ============================================================================
# SCREEN MASQUE : fond noir + masque bezier (silhouette ecran, 8 points)
# ============================================================================
masqueLayer = Oil.createObject("TextureLayer")
masqueLayer.label = "Masque"
masqueGen = Oil.createObject("UniformTextureGenerator")
masqueGen.resolution.width.set(1920)
masqueGen.resolution.height.set(1080)
masqueGen.color.red.set(0.0)
masqueGen.color.green.set(0.0)
masqueGen.color.blue.set(0.0)
masqueGen.color.alpha.set(1.0)

bezierPathGen = Oil.createObject("PathShapeGenerator")
bezierPathGen.path.closed.set(True)

points_data = [
    {"x": 0.96, "y": 0.5, "neg_x": 0.004544258117675781, "neg_y": 0.39047425985336304, "pos_x": 0.004544317722320557, "pos_y": -0.42278939485549927, "in": "quadratic", "out": "quadratic"},
    {"x": 0.92, "y": 0.05, "neg_x": 0.07845204323530197, "neg_y": 0.024760382249951363, "pos_x": -0.07845205068588257, "pos_y": -0.024760369211435318, "in": "linear", "out": "cubic"},
    {"x": 0.5, "y": 0.03, "neg_x": 0.21891722083091736, "neg_y": -0.000625459011644125, "pos_x": -0.21891722083091736, "pos_y": 0.0006254930049180984, "in": "quadratic", "out": "quadratic"},
    {"x": 0.07999999821186066, "y": 0.05000000074505806, "neg_x": 0.05869431793689728, "neg_y": -0.030146215111017227, "pos_x": -0.05869431421160698, "pos_y": 0.030146228149533272, "in": "cubic", "out": "linear"},
    {"x": 0.04, "y": 0.5, "neg_x": 0.004544302821159363, "neg_y": -0.3877813220024109, "pos_x": -0.001514773815870285, "pos_y": 0.4120177626609802, "in": "quadratic", "out": "quadratic"},
    {"x": 0.07999999821186066, "y": 0.949999988079071, "neg_x": -0.02423633262515068, "neg_y": -0.024236340075731277, "pos_x": 0.02423633448779583, "pos_y": 0.02423633635044098, "in": "linear", "out": "cubic"},
    {"x": 0.5, "y": 0.98, "neg_x": -0.11136850714683533, "neg_y": -0.0014644861221313477, "pos_x": 0.11136850714683533, "pos_y": 0.0014645034680142999, "in": "quadratic", "out": "quadratic"},
    {"x": 0.92, "y": 0.95, "neg_x": -0.016662482172250748, "neg_y": 0.045779742300510406, "pos_x": 0.0166624803096056, "pos_y": -0.045779746025800705, "in": "cubic", "out": "linear"},
]

for pdata in points_data:
    cp = Oil.createObject("Path2dControlPoint")
    cp.position.x = pdata["x"]
    cp.position.y = pdata["y"]
    cp.tangents.negative.x = pdata["neg_x"]
    cp.tangents.negative.y = pdata["neg_y"]
    cp.tangents.positive.x = pdata["pos_x"]
    cp.tangents.positive.y = pdata["pos_y"]
    cp.tangents.linked.set(True)
    cp.tangents.inputInterpolation.set(PATH_INTERP[pdata["in"]])
    cp.tangents.outputInterpolation.set(PATH_INTERP[pdata["out"]])
    bezierPathGen.path.points.append(cp)

bezierMask = Oil.createObject("ShapeTextureMask")
bezierMask.resolution.width.set(1920)
bezierMask.resolution.height.set(1080)
bezierMask.inverse.set(True)
bezierMask.shape = bezierPathGen
bezierMask.feather.enabled.set(True)
bezierMask.feather.width.set(66.5)

maskModMasque = Oil.createObject("MaskTextureModifier")
maskModMasque.label = "Mask"
maskModMasque.masks.append(bezierMask)
masqueGen.modifiers.append(maskModMasque)

masqueLayer.generator = masqueGen

screenMasqueCompo = Oil.createObject("Compo")
screenMasqueCompo.layers.append(masqueLayer)

screenMasqueLayer = Oil.createObject("TextureLayer")
screenMasqueLayer.generator = screenMasqueCompo
screenMasqueLayer.label = "Screen Masque"

# ============================================================================
# ASSEMBLAGE FINAL : Compo master + Parameters + Flicker + Compensation masques
# ============================================================================
mainCompo = Oil.createObject("Compo")
mainCompo.layers.append(traceLayer)
mainCompo.layers.append(screenLayer)
mainCompo.layers.append(screenMasqueLayer)

paramBank = Oil.createObject("ParameterBank")
paramBank.label = "Parameters"

# Band and levels exposed with the extractor's own units (Hz, dB): a Percentage parameter linked to them
# sends nonsense (band stuck at 22 Hz, range 0 dB -> 0 dB: the point never moves).
def addAudioParam(cls, label, value, target):
    p = Oil.createObject("Parameter(%s)" % cls)
    p.label = label
    p.value.set(value)
    t = Oil.createObject("ParameterLinkTarget")
    t.target.set(target)
    p.targets.append(t)
    paramBank.parameters.append(p)
    return p

freqMinParam = addAudioParam("Frequency", "Frequency Interval Min", FREQ_MIN, ySource.extractor.frequencyInterval.begin)
freqMaxParam = addAudioParam("Frequency", "Frequency Interval Max", FREQ_MAX, ySource.extractor.frequencyInterval.end)
ampMinParam = addAudioParam("Decibel", "Amplitude Interval Min", LEVEL_MIN, ySource.extractor.amplitudeInterval.begin)
ampMaxParam = addAudioParam("Decibel", "Amplitude Interval Max", LEVEL_MAX, ySource.extractor.amplitudeInterval.end)

# Position Y de Trace, exposee pour reglage manuel
traceYParam = Oil.createObject("Parameter(Percentage)")
traceYParam.label = "Trace Position Y"
traceYParam.value.set(0.584)
t = Oil.createObject("ParameterLinkTarget")
t.target.set(traceLayer.renderer.placement.position.y)
traceYParam.targets.append(t)
paramBank.parameters.append(traceYParam)

# Parametre combine : saturation backscreen + 2 intensites de blur, chacun avec sa PROPRE courbe
combinedParam = Oil.createObject("Parameter(Percentage)")
combinedParam.label = "backscreen Begin Color -> Saturation, Grid Gaussian Blur Intensity and Trace Gaussian Blur Intensity"
combinedParam.value.set(0.4735388187566647)

t1 = Oil.createObject("ParameterLinkTarget")
t1.target.set(bgGradient.beginColor.saturation)
t1.modifiers.append(makeKeyframeCurve([
    {"position": 0.0, "key": 0.4141103202846978},
    {"position": 1.0, "key": 0.6148042704626335},
]))
combinedParam.targets.append(t1)

t2 = Oil.createObject("ParameterLinkTarget")
t2.target.set(gridBlurMod.intensity)
t2.modifiers.append(makeKeyframeCurve([
    {"position": 0.0024070021881838076, "key": 0.8807829181494662},
    {"position": 1.0, "key": 1.0},
]))
combinedParam.targets.append(t2)

t3 = Oil.createObject("ParameterLinkTarget")
t3.target.set(traceBlur.intensity)
t3.modifiers.append(makeKeyframeCurve([
    {"position": 0.0024070021881838076, "key": 0.8807829181494662},
    {"position": 1.0, "key": 1.0},
]))
combinedParam.targets.append(t3)

paramBank.parameters.append(combinedParam)
mainCompo.tools.append(paramBank)

# --- Flicker : bruit Simplex (deja la valeur par defaut) qui anime combinedParam.value ---
flickerCue = Oil.createObject("FunctionCue(Percentage)")
flickerCue.label = "Screen Flickering + Blur"
flickerShape = Oil.createObject("NoiseFunctionShape")
flickerShape.frequency.set(10.0)
flickerShape.contrast.set(0.0)

flickerFunction = Oil.createObject("ParametricScalarFunction({input = Seconds, output = Percentage})")
flickerFunction.shape = flickerShape
flickerFunction.parameters.minimum = 0.0
flickerFunction.parameters.maximum = 1.0
flickerFunction.parameters.period = 3.0
flickerFunction.parameters.offset = 0.0
flickerFunction.parameters.phase = 0.5
flickerFunction.parameters.repetitions = 1
flickerFunction.parameters.wrapMode.set(WRAP_MODE_REPEAT)

flickerCue.function = flickerFunction
flickerCue.parameters.looping = True
flickerCue.parameters.launchMode.set(LAUNCH_MODE_RESTART_WITH_ACTIVATION)
flickerCue.transport.length = 3.0

flickerTarget = Oil.createObject("ParameterLinkTarget")
flickerTarget.target.set(combinedParam.value)
flickerCue.targets.append(flickerTarget)

mainAnimBank = Oil.createObject("AnimationBank")
mainAnimBank.label = "Animations"
mainAnimBank.animations.append(flickerCue)
mainCompo.tools.append(mainAnimBank)
flickerCue.transport.play.trig()

# --- Compensation Y : quand on bouge Trace Position Y, ces 3 masques (imbriques dans
# Trace) doivent rester fixes a l'ecran -> chacun recoit l'inverse (1-x) du deplacement,
# sauf le Placement Mask du Traceur qui a besoin du sens direct (x). ---
compLinkBank = Oil.createObject("LinkBank")
compLinkBank.label = "Circle Mask Compensation"

def addCompensationLink(label, targetVar, inverted=True):
    curve = makeKeyframeCurve(
        [{"position": 0.0, "key": 1.0}, {"position": 1.0, "key": 0.0}] if inverted
        else [{"position": 0.0, "key": 0.0}, {"position": 1.0, "key": 1.0}]
    )
    source = Oil.createObject("ParameterLinkSource")
    source.target.set(traceYParam.value)
    target = Oil.createObject("ParameterLinkTarget")
    target.target.set(targetVar)
    target.modifiers.append(curve)
    link = Oil.createObject("Link")
    link.label = label
    link.source = source
    link.targets.append(target)
    compLinkBank.links.append(link)

addCompensationLink("Circle Mask Y Compensation", transformCircleMask.shape.placement.position.y, inverted=True)
addCompensationLink("Mask Circle Mask Y Compensation", crtShapeMask.shape.placement.position.y, inverted=True)
addCompensationLink("Placement Mask Y Compensation", travelMask.placement.position.y, inverted=False)

mainCompo.tools.append(compLinkBank)

# --- Wrap final + insertion dans la scene ---
oscLayer = Oil.createObject("TextureLayer")
oscLayer.generator = mainCompo
oscLayer.label = OSC_LABEL
oscLayer.renderer.placement.verticalFlip = False
script.parentElement.layers.append(oscLayer)

# The circle sizes (point, circle masks) are put back to 500 px by SMODE one or two frames AFTER this script ends:
# setting them here is not enough, the Trace Writer writes them again during its first frames.

result = (f"{OSC_LABEL} recree : {N_POINTS} points, {N_ECHOES} echos, audio {FREQ_MIN:.0f}-{FREQ_MAX:.0f} Hz "
          f"({LEVEL_MIN:.0f} a {LEVEL_MAX:.0f} dB) sur {dsDevice.getFriendlyName()} / {audioChannel.getFriendlyName()}")
