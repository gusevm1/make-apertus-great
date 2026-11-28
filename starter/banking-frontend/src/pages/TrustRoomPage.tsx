import { config } from "../config";
import { TrustRoomFrame } from "../trustroom/TrustRoomFrame";
import { TrustRoomPlaceholder } from "../trustroom/TrustRoomPlaceholder";
import styles from "./TrustRoomPage.module.css";

/** Full-page TrustRoom (`/trustroom`), same embedding as the panel with mode=fullpage. */
export function TrustRoomPage() {
  return (
    <div className={styles.frame}>
      {config.trustroomUrl ? <TrustRoomFrame mode="fullpage" visible /> : <TrustRoomPlaceholder />}
    </div>
  );
}
