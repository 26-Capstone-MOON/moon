package com.moonapp.widget

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.facebook.react.ReactApplication
import com.facebook.react.bridge.ReactContext
import com.facebook.react.modules.core.DeviceEventManagerModule

/**
 * 잠금화면 위젯 "질문하기" 액션 → BroadcastReceiver → JS DeviceEventEmitter.
 * - ReactContext가 살아있으면 즉시 'WidgetMicTriggered' 이벤트 발사
 * - 죽어있으면 SharedPreferences에 pending 플래그+timestamp 저장 (backup path)
 *   → MainActivity.onResume에서 [tryConsumePendingTrigger]로 재시도.
 */
class WidgetMicActionReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        Log.d(TAG, "onReceive — action=${intent.action}")
        if (!emitIfReady(context)) {
            markPending(context)
        }
    }

    companion object {
        private const val TAG = "WidgetMicReceiver"
        const val ACTION_MIC_TRIGGER = "com.moonapp.widget.action.MIC_TRIGGER"
        const val EVENT_NAME = "WidgetMicTriggered"

        private const val PREFS_NAME = "moon_widget_prefs"
        private const val KEY_PENDING_AT = "pending_mic_trigger_at"
        // 트리거 발생 후 30초가 지나면 무시. 사용자가 잠금화면 탭한 직후 앱을 여는
        // 시간을 충분히 커버하면서 너무 오래된 트리거가 부활하는 건 막는다.
        private const val MAX_AGE_MS = 30_000L
        // ReactContext가 아직 안 떴을 때 폴링 간격 / 최대 재시도 횟수
        private const val POLL_INTERVAL_MS = 300L
        private const val MAX_POLL_ATTEMPTS = 20  // 약 6초

        /**
         * 즉시 emit 시도. ReactContext가 살아있고 emit 성공 시 true.
         */
        private fun emitIfReady(context: Context): Boolean {
            val app = context.applicationContext as? ReactApplication
            if (app == null) {
                Log.w(TAG, "applicationContext is not ReactApplication")
                return false
            }
            val reactContext: ReactContext? = app.reactHost?.currentReactContext
            if (reactContext == null) {
                Log.w(TAG, "ReactContext not ready — falling back to pending flag")
                return false
            }
            return try {
                reactContext
                    .getJSModule(DeviceEventManagerModule.RCTDeviceEventEmitter::class.java)
                    .emit(EVENT_NAME, null)
                Log.d(TAG, "emitted $EVENT_NAME")
                true
            } catch (e: Exception) {
                Log.e(TAG, "failed to emit $EVENT_NAME", e)
                false
            }
        }

        private fun markPending(context: Context) {
            val prefs = context.applicationContext.getSharedPreferences(
                PREFS_NAME, Context.MODE_PRIVATE,
            )
            val now = System.currentTimeMillis()
            prefs.edit().putLong(KEY_PENDING_AT, now).apply()
            Log.d(TAG, "marked pending mic trigger at $now")
        }

        private fun clearPending(context: Context) {
            val prefs = context.applicationContext.getSharedPreferences(
                PREFS_NAME, Context.MODE_PRIVATE,
            )
            prefs.edit().remove(KEY_PENDING_AT).apply()
        }

        /**
         * MainActivity.onResume에서 호출. pending 플래그가 있고 시간이 너무 오래되지
         * 않았다면 ReactContext가 준비될 때까지 짧게 폴링하며 emit을 재시도한다.
         */
        fun tryConsumePendingTrigger(context: Context) {
            val prefs = context.applicationContext.getSharedPreferences(
                PREFS_NAME, Context.MODE_PRIVATE,
            )
            val pendingAt = prefs.getLong(KEY_PENDING_AT, 0L)
            if (pendingAt == 0L) return

            val age = System.currentTimeMillis() - pendingAt
            if (age > MAX_AGE_MS) {
                Log.d(TAG, "pending trigger expired (age=${age}ms) — discarding")
                clearPending(context)
                return
            }

            Log.d(TAG, "pending mic trigger found (age=${age}ms) — polling for ReactContext")
            val handler = Handler(Looper.getMainLooper())
            var attempts = 0
            handler.post(object : Runnable {
                override fun run() {
                    if (emitIfReady(context)) {
                        clearPending(context)
                        return
                    }
                    attempts++
                    if (attempts >= MAX_POLL_ATTEMPTS) {
                        Log.w(TAG, "ReactContext never came up — discarding pending trigger")
                        clearPending(context)
                        return
                    }
                    handler.postDelayed(this, POLL_INTERVAL_MS)
                }
            })
        }
    }
}
