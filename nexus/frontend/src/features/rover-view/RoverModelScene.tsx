import { Component, Suspense, useEffect, useMemo, useState, type ErrorInfo, type ReactNode } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { CameraControls, CameraControlsImpl, Grid, useGLTF, useProgress } from '@react-three/drei';
import { Box3, Raycaster, Vector2, Vector3, type Object3D } from 'three';
import styles from './RoverModelScene.module.css';

const MODEL_URL = '/assets/models/kanga-assembly.glb';
const VIEW_DIRECTION = new Vector3(1, 0.75, 1.35).normalize();

interface ModelExtent { size: number; height: number; object: Object3D }

const { ACTION } = CameraControlsImpl;
const MOUSE_BUTTONS = { left: ACTION.TRUCK, middle: ACTION.TRUCK, right: ACTION.ROTATE, wheel: ACTION.DOLLY } as const;

function RoverModel({ onReady }: { onReady: (extent: ModelExtent) => void }) {
  const { scene } = useGLTF(MODEL_URL);
  const { model, extent } = useMemo(() => {
    const model = scene.clone(true);
    const box = new Box3().setFromObject(model);
    const center = box.getCenter(new Vector3());
    const dimensions = box.getSize(new Vector3());
    model.position.set(-center.x, -box.min.y, -center.z);
    // The assembly is static until joint telemetry drives it, so skip per-frame matrix recomputation.
    model.traverse((object) => {
      object.updateMatrix();
      object.matrixAutoUpdate = false;
    });
    return { model, extent: { size: Math.max(dimensions.x, dimensions.y, dimensions.z) || 1, height: dimensions.y, object: model } };
  }, [scene]);

  useEffect(() => onReady(extent), [extent, onReady]);

  return <primitive object={model} dispose={null} />;
}

const useCameraControls = () => useThree((state) => state.controls) as unknown as CameraControlsImpl | null;

function CameraRig({ extent, resetToken }: { extent: ModelExtent; resetToken: number }) {
  const camera = useThree((state) => state.camera);
  const controls = useCameraControls();

  useEffect(() => {
    if (!controls) return;
    camera.near = extent.size / 1000;
    camera.far = extent.size * 200;
    camera.updateProjectionMatrix();
    const target = new Vector3(0, extent.height * 0.4, 0);
    const position = VIEW_DIRECTION.clone().multiplyScalar(extent.size * 2.3).add(target);
    // Cursor-based orbiting changes the focal offset independently of the look-at target.
    void controls.setFocalOffset(0, 0, 0, resetToken > 0);
    void controls.setLookAt(position.x, position.y, position.z, target.x, target.y, target.z, resetToken > 0);
  }, [camera, controls, extent, resetToken]);

  return null;
}

function CursorPivot({ model }: { model: Object3D }) {
  const camera = useThree((state) => state.camera);
  const canvas = useThree((state) => state.gl.domElement);
  const controls = useCameraControls();

  useEffect(() => {
    if (!controls) return;
    const raycaster = new Raycaster();
    const pointer = new Vector2();
    const pickPivot = (event: PointerEvent) => {
      if (event.button !== 2 || !controls.enabled) return;
      const rect = canvas.getBoundingClientRect();
      pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      const [hit] = raycaster.intersectObject(model, true);
      if (!hit) return;
      controls.stop();
      controls.setOrbitPoint(hit.point.x, hit.point.y, hit.point.z);
    };
    // Capture runs before camera-controls' own pointerdown handler, so the rotation starts around the new pivot.
    canvas.addEventListener('pointerdown', pickPivot, { capture: true });
    return () => canvas.removeEventListener('pointerdown', pickPivot, { capture: true });
  }, [camera, canvas, controls, model]);

  return null;
}

function RedrawOnResize() {
  const size = useThree((state) => state.size);
  const invalidate = useThree((state) => state.invalidate);
  useEffect(() => invalidate(), [size, invalidate]);
  return null;
}

function gridStep(size: number) {
  return 10 ** Math.floor(Math.log10(size / 2));
}

function LoadStatus() {
  const { active, progress } = useProgress();
  if (!active) return null;
  return <div className={styles.loading}><i style={{ width: `${progress}%` }} /><span>Loading rover model · {Math.round(progress)}%</span></div>;
}

interface BoundaryProps { children: ReactNode; onError: () => void }
interface BoundaryState { failed: boolean }

class ModelErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState { return { failed: true }; }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Rover model renderer failed', error, info);
    this.props.onError();
  }

  render() { return this.state.failed ? null : this.props.children; }
}

interface RoverModelSceneProps { sceneKey: number; resetToken: number; interactive: boolean; onError: () => void }

export function RoverModelScene({ sceneKey, resetToken, interactive, onError }: RoverModelSceneProps) {
  const [extent, setExtent] = useState<ModelExtent | null>(null);
  const size = extent?.size ?? 1;
  const step = gridStep(size);

  return (
    <div className={styles.scene}>
      <ModelErrorBoundary key={sceneKey} onError={onError}>
        <Canvas
          key={sceneKey}
          frameloop="demand"
          camera={{ position: [4, 3, 6], fov: 38 }}
          dpr={[1, 1.25]}
          gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
          onContextMenu={(event) => event.preventDefault()}
        >
          <ambientLight intensity={0.35} />
          <hemisphereLight args={['#dfe6ff', '#15171b', 0.55]} />
          <directionalLight position={[5, 8, 4]} intensity={1.1} />
          <directionalLight position={[-5, 3, -4]} intensity={0.3} color="#8ea4ff" />
          <Suspense fallback={null}>
            <RoverModel onReady={setExtent} />
          </Suspense>
          {extent && (
            <Grid
              infiniteGrid
              cellSize={step}
              sectionSize={step * 5}
              cellThickness={0.6}
              sectionThickness={1}
              cellColor="#161c33"
              sectionColor="#1a2f7a"
              fadeDistance={size * 12}
              fadeStrength={1.5}
            />
          )}
          <CameraControls
            makeDefault
            enabled={interactive}
            mouseButtons={MOUSE_BUTTONS}
            dollyToCursor
            infinityDolly
            smoothTime={0.15}
            draggingSmoothTime={0.05}
            maxPolarAngle={Math.PI / 2 - 0.02}
            minDistance={size * 0.05}
            maxDistance={size * 15}
          />
          {extent && <CameraRig extent={extent} resetToken={resetToken} />}
          {extent && <CursorPivot model={extent.object} />}
          <RedrawOnResize />
        </Canvas>
      </ModelErrorBoundary>
      <LoadStatus />
    </div>
  );
}

useGLTF.preload(MODEL_URL);
