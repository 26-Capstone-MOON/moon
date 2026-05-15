package com.moonapp.widget

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.bridge.ReadableMap

class NavigationNotificationModule(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    override fun getName(): String = NAME

    @ReactMethod
    fun start(params: ReadableMap, promise: Promise) {
        try {
            requestPostNotificationsPermissionIfNeeded()
            sendServiceIntent(NavigationForegroundService.ACTION_START, params)
            promise.resolve(null)
        } catch (e: Exception) {
            Log.e(NAME, "start failed", e)
            promise.reject(ERR_START, e)
        }
    }

    @ReactMethod
    fun update(params: ReadableMap, promise: Promise) {
        try {
            sendServiceIntent(NavigationForegroundService.ACTION_UPDATE, params)
            promise.resolve(null)
        } catch (e: Exception) {
            Log.e(NAME, "update failed", e)
            promise.reject(ERR_UPDATE, e)
        }
    }

    @ReactMethod
    fun stop(promise: Promise) {
        try {
            sendServiceIntent(NavigationForegroundService.ACTION_STOP, null)
            promise.resolve(null)
        } catch (e: Exception) {
            Log.e(NAME, "stop failed", e)
            promise.reject(ERR_STOP, e)
        }
    }

    /** Kept for one-tap manual testing during development. */
    @ReactMethod
    fun startDummy() {
        Log.d(NAME, "startDummy called")
        requestPostNotificationsPermissionIfNeeded()
        val context = reactApplicationContext
        val intent = Intent(context, NavigationForegroundService::class.java).apply {
            action = NavigationForegroundService.ACTION_START
        }
        ContextCompat.startForegroundService(context, intent)
    }

    private fun sendServiceIntent(actionName: String, params: ReadableMap?) {
        val context = reactApplicationContext
        val intent = Intent(context, NavigationForegroundService::class.java).apply {
            action = actionName
            params?.let { applyParams(it) }
        }
        ContextCompat.startForegroundService(context, intent)
    }

    private fun Intent.applyParams(params: ReadableMap) {
        if (params.hasKey(KEY_LABEL) && !params.isNull(KEY_LABEL)) {
            putExtra(NavigationForegroundService.EXTRA_LABEL, params.getString(KEY_LABEL))
        }
        if (params.hasKey(KEY_PRIMARY) && !params.isNull(KEY_PRIMARY)) {
            putExtra(NavigationForegroundService.EXTRA_PRIMARY, params.getString(KEY_PRIMARY))
        }
        if (params.hasKey(KEY_NEXT) && !params.isNull(KEY_NEXT)) {
            putExtra(NavigationForegroundService.EXTRA_NEXT, params.getString(KEY_NEXT))
        }
        if (params.hasKey(KEY_ARROW_TYPE) && !params.isNull(KEY_ARROW_TYPE)) {
            putExtra(NavigationForegroundService.EXTRA_ARROW_TYPE, params.getString(KEY_ARROW_TYPE))
        }
        if (params.hasKey(KEY_PROGRESS) && !params.isNull(KEY_PROGRESS)) {
            putExtra(NavigationForegroundService.EXTRA_PROGRESS, params.getInt(KEY_PROGRESS))
        }
        if (params.hasKey(KEY_CURRENT_INDEX) && !params.isNull(KEY_CURRENT_INDEX)) {
            putExtra(
                NavigationForegroundService.EXTRA_CURRENT_INDEX,
                params.getInt(KEY_CURRENT_INDEX),
            )
        }
        if (params.hasKey(KEY_TOTAL_COUNT) && !params.isNull(KEY_TOTAL_COUNT)) {
            putExtra(
                NavigationForegroundService.EXTRA_TOTAL_COUNT,
                params.getInt(KEY_TOTAL_COUNT),
            )
        }
        if (params.hasKey(KEY_DP_TYPES) && !params.isNull(KEY_DP_TYPES)) {
            val arr = params.getArray(KEY_DP_TYPES)
            val list = ArrayList<String>()
            if (arr != null) {
                for (i in 0 until arr.size()) {
                    arr.getString(i)?.let { list.add(it) }
                }
            }
            putStringArrayListExtra(NavigationForegroundService.EXTRA_DP_TYPES, list)
        }
        if (params.hasKey(KEY_IS_LISTENING) && !params.isNull(KEY_IS_LISTENING)) {
            putExtra(
                NavigationForegroundService.EXTRA_IS_LISTENING,
                params.getBoolean(KEY_IS_LISTENING),
            )
        }
    }

    private fun requestPostNotificationsPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val activity = reactApplicationContext.currentActivity ?: return
        val granted = ContextCompat.checkSelfPermission(
            activity,
            Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
        if (granted) return
        ActivityCompat.requestPermissions(
            activity,
            arrayOf(Manifest.permission.POST_NOTIFICATIONS),
            PERMISSION_REQUEST_CODE,
        )
    }

    companion object {
        const val NAME = "NavigationNotification"
        private const val PERMISSION_REQUEST_CODE = 2001

        private const val KEY_LABEL = "label"
        private const val KEY_PRIMARY = "primary"
        private const val KEY_NEXT = "next"
        private const val KEY_ARROW_TYPE = "arrowType"
        private const val KEY_PROGRESS = "progress"
        private const val KEY_CURRENT_INDEX = "currentIndex"
        private const val KEY_TOTAL_COUNT = "totalCount"
        private const val KEY_DP_TYPES = "dpTypes"
        private const val KEY_IS_LISTENING = "isListening"

        private const val ERR_START = "E_WIDGET_START"
        private const val ERR_UPDATE = "E_WIDGET_UPDATE"
        private const val ERR_STOP = "E_WIDGET_STOP"
    }
}
