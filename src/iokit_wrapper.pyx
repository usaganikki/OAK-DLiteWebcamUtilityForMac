# distutils: language=c
# distutils: extra_link_args=['-framework', 'IOKit', '-framework', 'CoreFoundation']

from libc.stdlib cimport malloc, free
from libc.string cimport strlen, strcpy, memcpy
import sys
# Pythonのthreadingモジュールをインポート (GIL操作に必要)
import threading

# --- CoreFoundation の C API 宣言を先に ---
cdef extern from "CoreFoundation/CoreFoundation.h":
    ctypedef const void* CFTypeRef # void* から const void* へ (より正確)
    ctypedef CFTypeRef CFStringRef
    ctypedef CFTypeRef CFAllocatorRef
    ctypedef CFTypeRef CFDictionaryRef
    ctypedef CFTypeRef CFMutableDictionaryRef
    ctypedef CFTypeRef CFNumberRef
    ctypedef CFTypeRef CFRunLoopRef
    ctypedef CFTypeRef CFRunLoopSourceRef
    ctypedef long CFIndex
    ctypedef unsigned char Boolean

    # 定数
    cdef CFAllocatorRef kCFAllocatorDefault
    cdef CFStringRef kCFRunLoopDefaultMode

    # 文字列関数
    CFStringRef CFStringCreateWithCString(
        CFAllocatorRef alloc,
        const char* cStr,
        unsigned int encoding # CFStringEncoding
    )
    Boolean CFStringGetCString(
        CFStringRef theString,
        char* buffer,
        CFIndex bufferSize,
        unsigned int encoding # CFStringEncoding
    )
    CFIndex CFStringGetLength(CFStringRef theString)

    # メモリ管理
    void CFRelease(CFTypeRef cf)
    CFTypeRef CFRetain(CFTypeRef cf)

    # 辞書操作
    CFTypeRef CFDictionaryGetValue(CFDictionaryRef theDict, const void* key) # void* から const void* へ
    void CFDictionarySetValue(CFMutableDictionaryRef theDict, const void* key, const void* value)
    CFMutableDictionaryRef CFDictionaryCreateMutable(
        CFAllocatorRef allocator,
        CFIndex capacity,
        const void* keyCallBacks, # const CFDictionaryKeyCallBacks*
        const void* valueCallBacks # const CFDictionaryValueCallBacks*
    )
    # 辞書コールバック定数 (通常はNULLを渡すことが多い)
    # extern const CFDictionaryKeyCallBacks kCFTypeDictionaryKeyCallBacks
    # extern const CFDictionaryValueCallBacks kCFTypeDictionaryValueCallBacks

    # 型チェック
    unsigned long CFGetTypeID(CFTypeRef cf) # CFTypeID
    unsigned long CFStringGetTypeID() # CFTypeID
    unsigned long CFDictionaryGetTypeID() # CFTypeID
    unsigned long CFNumberGetTypeID() # CFTypeID

    # 数値型
    ctypedef enum CFNumberType:
        kCFNumberSInt8Type, kCFNumberSInt16Type, kCFNumberSInt32Type, kCFNumberSInt64Type,
        kCFNumberFloat32Type, kCFNumberFloat64Type,
        kCFNumberCharType, kCFNumberShortType, kCFNumberIntType, kCFNumberLongType,
        kCFNumberLongLongType, kCFNumberFloatType, kCFNumberDoubleType,
        kCFNumberCFIndexType, kCFNumberNSIntegerType, kCFNumberCGFloatType,
        kCFNumberMaxType

    CFNumberRef CFNumberCreate(CFAllocatorRef allocator, CFNumberType theType, const void* valuePtr)
    Boolean CFNumberGetValue(CFNumberRef number, CFNumberType theType, void* valuePtr)


    # RunLoop API
    CFRunLoopRef CFRunLoopGetCurrent()
    CFRunLoopRef CFRunLoopGetMain()
    void CFRunLoopAddSource(CFRunLoopRef rl, CFRunLoopSourceRef source, CFStringRef mode)
    void CFRunLoopRemoveSource(CFRunLoopRef rl, CFRunLoopSourceRef source, CFStringRef mode)
    void CFRunLoopRun()
    void CFRunLoopStop(CFRunLoopRef rl)

# --- IOKit の C API 宣言 ---
cdef extern from "IOKit/IOKitLib.h":
    ctypedef unsigned int io_object_t
    ctypedef io_object_t io_service_t
    ctypedef io_object_t io_iterator_t
    ctypedef unsigned int kern_return_t
    ctypedef unsigned int mach_port_t # Changed from 'mach_port_t mach_port_t'

    # 定数
    cdef mach_port_t kIOMasterPortDefault # macOS 12以降は kIOMainPortDefault
    cdef kern_return_t KERN_SUCCESS

    # 基本関数
    void* IOServiceMatching(const char* name)
    kern_return_t IOServiceGetMatchingServices(
        mach_port_t masterPort,
        CFDictionaryRef matching, # void* から CFDictionaryRef に変更
        io_iterator_t* existing
    )
    io_service_t IOIteratorNext(io_iterator_t iterator)
    kern_return_t IOObjectRelease(io_object_t object) # unsigned int から io_object_t に変更

    # プロパティ取得
    CFTypeRef IORegistryEntryCreateCFProperty( # void* から CFTypeRef に変更
        io_service_t entry,
        CFStringRef key, # void* から CFStringRef に変更
        CFAllocatorRef allocator,
        unsigned int options
    )
    kern_return_t IORegistryEntryGetRegistryEntryID(io_service_t entry, unsigned long long *entryID)


    # --- 通知関連 API ---
    ctypedef void (*IOServiceMatchingCallback)(
        void* refcon,
        io_iterator_t iterator
    ) # This callback should be noexcept if the C code expects it.
    ctypedef void* IONotificationPortRef

    IONotificationPortRef IONotificationPortCreate(mach_port_t masterPort)
    void IONotificationPortDestroy(IONotificationPortRef notify)
    CFRunLoopSourceRef IONotificationPortGetRunLoopSource(IONotificationPortRef notify)

    kern_return_t IOServiceAddMatchingNotification(
        IONotificationPortRef notifyPort,
        const char* notificationType, # e.g., kIOMatchedNotification
        CFDictionaryRef matching,       # Consumed by this function
        IOServiceMatchingCallback callback,
        void* refCon,
        io_iterator_t* notificationIterator
    )

cdef extern from "IOKit/usb/IOUSBLib.h": # For kUSBVendorID, kUSBProductID (actual string constants)
    # These are CFStringRef constants in ObjC, e.g. extern const CFStringRef kUSBVendorID;
    # We will create them manually using their string values "idVendor", "idProduct".
    # We will define them as Python bytes and convert to CFStringRef later if needed
    # Or, more commonly, use them as keys in a CFDictionary directly if they are CFStringRef
    pass # No direct cdef needed if we create CFString keys manually

# --- Python文字列からCFStringRefを作成するヘルパー ---
cdef CFStringRef _py_str_to_cfstring(str py_str) except NULL:
    cdef bytes byte_str = py_str.encode('utf-8')
    cdef const char* c_str = byte_str
    return CFStringCreateWithCString(kCFAllocatorDefault, c_str, kCFStringEncodingUTF8)

# UTF-8エンコーディング定数
cdef unsigned int kCFStringEncodingUTF8 = 0x08000100

# --- IOKit USB Vendor/Product ID Keys (as Python strings for CFString creation) ---
# These are defined as extern CFStringRef const kUSBVendorID; in IOKit/usb/USB.h
# For Cython, it's often easier to recreate them or use their string values if known.
# The actual string values are "idVendor" and "idProduct".
USB_VENDOR_ID_KEY = "idVendor"
USB_PRODUCT_ID_KEY = "idProduct"
IO_PLATFORM_SERIAL_NUMBER_KEY = "IOPlatformSerialNumber"

# --- Notification types (as bytes for IOServiceAddMatchingNotification) ---
# These are extern const char kIOMatchedNotification[];
K_IO_MATCHED_NOTIFICATION = b"IOServiceMatched"
K_IO_TERMINATED_NOTIFICATION = b"IOServiceTerminated"


class IOKitError(Exception):
    """IOKit操作エラー"""
    pass

# --- Globals for USB Monitoring ---
cdef IONotificationPortRef g_notify_port = NULL
cdef CFRunLoopSourceRef g_run_loop_source = NULL
cdef CFRunLoopRef g_event_loop_run_loop_ref = NULL # Store the RunLoop of the event thread
cdef io_iterator_t g_matched_iterator = 0
cdef io_iterator_t g_terminated_iterator = 0
cdef object g_python_callback_handler = None
cdef bint g_monitoring_active = False


# --- Helper function to get a long property from a service ---
cdef long _get_long_property(io_service_t service, const char* key_c_str):
    cdef CFStringRef key_cf_str = NULL
    cdef CFNumberRef value_cf_num = NULL
    cdef long value = -1 # Default if not found or error
    cdef long long value_ll = -1 # For CFNumberGetValue

    key_cf_str = CFStringCreateWithCString(kCFAllocatorDefault, key_c_str, kCFStringEncodingUTF8)
    if key_cf_str == NULL:
        return value

    value_cf_num = <CFNumberRef>IORegistryEntryCreateCFProperty(service, key_cf_str, kCFAllocatorDefault, 0)
    if value_cf_num != NULL:
        if CFGetTypeID(value_cf_num) == CFNumberGetTypeID():
            CFNumberGetValue(value_cf_num, kCFNumberLongLongType, &value_ll)
            value = <long>value_ll
        CFRelease(value_cf_num)
    
    CFRelease(key_cf_str)
    return value

# --- Helper function to get a string property from a service ---
cdef str _get_string_property(io_service_t service, const char* key_c_str):
    cdef CFStringRef key_cf_str = NULL
    cdef CFStringRef value_cf_str = NULL
    cdef str py_str = None

    key_cf_str = CFStringCreateWithCString(kCFAllocatorDefault, key_c_str, kCFStringEncodingUTF8)
    if key_cf_str == NULL:
        return py_str

    value_cf_str = <CFStringRef>IORegistryEntryCreateCFProperty(service, key_cf_str, kCFAllocatorDefault, 0)
    if value_cf_str != NULL:
        if CFGetTypeID(value_cf_str) == CFStringGetTypeID():
            py_str = _cfstring_to_python(value_cf_str)
        CFRelease(value_cf_str)
            
    CFRelease(key_cf_str)
    return py_str if py_str is not None else "N/A"

# --- Helper function to get service ID ---
cdef unsigned long long _get_service_id(io_service_t service):
    cdef unsigned long long entry_id = 0
    IORegistryEntryGetRegistryEntryID(service, &entry_id)
    return entry_id

# --- C Callback for USB Device Events ---
cdef void _usb_device_event_callback(void* refCon, io_iterator_t iterator) noexcept with gil:
    print(f"[iokit_wrapper_callback] _usb_device_event_callback called. refCon (addr): {<Py_ssize_t>refCon}")
    # This callback must not propagate Python exceptions to C code.
    # It runs with the GIL acquired, as we'll call Python code.
    cdef io_service_t usb_device
    cdef int vendor_id
    cdef int product_id
    cdef str serial_number
    cdef unsigned long long service_id
    
    # Extract Python handler and event type from refCon
    # This assumes refCon is a pointer to a Python tuple stored by Cython.
    # A safer way is to pass a C struct pointer or manage refCon carefully.
    # For simplicity, we assume g_python_callback_handler is set.
    # A better approach for event type: pass a small int/bool as part of refCon.
    # For now, we'll rely on separate iterators for matched/terminated.
    # This callback will be used for BOTH matched and terminated.
    # We need a way to know which event it is.
    # One way: check which global iterator (g_matched_iterator or g_terminated_iterator) matches `iterator`.
    # This is not robust. Better: use different refCon for different notifications.
    # Let's assume refCon is a simple int: 1 for matched, 0 for terminated.

    is_connected_event = <bint>(<Py_ssize_t>refCon) # Cast void* to Py_ssize_t then to bint
    print(f"[iokit_wrapper_callback] is_connected_event: {is_connected_event}")

    if g_python_callback_handler is None:
        print("[iokit_wrapper_callback] Python callback handler is None in C callback.")
        return

    # print(f"Debug: _usb_device_event_callback called. Event type: {'connect' if is_connected_event else 'disconnect'}")
    print(f"[iokit_wrapper_callback] Processing devices in iterator...")
    while True:
        usb_device = IOIteratorNext(iterator)
        if usb_device == 0:
            break

        vendor_id = _get_long_property(usb_device, USB_VENDOR_ID_KEY.encode('utf-8'))
        product_id = _get_long_property(usb_device, USB_PRODUCT_ID_KEY.encode('utf-8'))
        serial_number = _get_string_property(usb_device, IO_PLATFORM_SERIAL_NUMBER_KEY.encode('utf-8'))
        service_id = _get_service_id(usb_device)
        
        print(f"[iokit_wrapper_callback] Device event: VID={vendor_id:04x}, PID={product_id:04x}, SN='{serial_number}', ServiceID={service_id}")

        try:
            if is_connected_event:
                if hasattr(g_python_callback_handler, 'on_device_connected'):
                    g_python_callback_handler.on_device_connected(vendor_id, product_id, serial_number, service_id)
            else:
                if hasattr(g_python_callback_handler, 'on_device_disconnected'):
                    g_python_callback_handler.on_device_disconnected(vendor_id, product_id, serial_number, service_id)
        except Exception as e: # Catch any Python exception
            # In a real app, log this error properly
            # print(f"Error in Python callback: {e!r}")
            print(f"[iokit_wrapper_callback] Exception in Python callback: {e!r}")
            pass # Do not let exceptions escape to C.

        IOObjectRelease(usb_device)
    print(f"[iokit_wrapper_callback] Finished processing devices in iterator.")
    return # Explicit return for noexcept void function


# --- Python-callable functions for USB Monitoring ---
def init_usb_monitoring(object callback_handler, int vid, int pid):
    global g_notify_port, g_run_loop_source, g_python_callback_handler
    global g_matched_iterator, g_terminated_iterator, g_monitoring_active
    print("[iokit_wrapper] init_usb_monitoring: Start")

    if g_monitoring_active:
        print("[iokit_wrapper] USB monitoring is already active.")
        return True

    g_python_callback_handler = callback_handler
    print(f"[iokit_wrapper] Python callback handler set: {g_python_callback_handler}") # This is a Python object, should be fine

    g_notify_port = IONotificationPortCreate(kIOMasterPortDefault)
    print(f"[iokit_wrapper] IONotificationPortCreate result (addr): {<Py_ssize_t>g_notify_port}")
    if g_notify_port == NULL:
        raise IOKitError("Failed to create IONotificationPort")

    g_run_loop_source = IONotificationPortGetRunLoopSource(g_notify_port)
    print(f"[iokit_wrapper] IONotificationPortGetRunLoopSource result (addr): {<Py_ssize_t>g_run_loop_source}")
    if g_run_loop_source == NULL:
        IONotificationPortDestroy(g_notify_port)
        g_notify_port = NULL
        raise IOKitError("Failed to get RunLoopSource from IONotificationPort")

    # --- Create Matching Dictionary ---
    print("[iokit_wrapper] Creating matching dictionary...")
    # Match IOUSBDevice class (or IOUSBHostDevice on newer macOS for some devices)
    cdef CFMutableDictionaryRef matching_dict = IOServiceMatching(b"IOUSBDevice")
    print(f"[iokit_wrapper] IOServiceMatching result (addr): {<Py_ssize_t>matching_dict}")
    if matching_dict == NULL:
        IONotificationPortDestroy(g_notify_port)
        g_notify_port = NULL
        raise IOKitError("IOServiceMatching failed to create a dictionary for IOUSBDevice")

    # Add Vendor ID to matching dictionary
    print(f"[iokit_wrapper] Adding VID {vid:04x} to matching dictionary...")
    cdef long vendor_id_val = vid
    cdef CFNumberRef vid_cf = CFNumberCreate(kCFAllocatorDefault, kCFNumberLongType, &vendor_id_val)
    if vid_cf == NULL:
        CFRelease(matching_dict)
        IONotificationPortDestroy(g_notify_port)
        g_notify_port = NULL
        raise IOKitError("CFNumberCreate failed for Vendor ID")
    
    # Use Python string for key, then convert to CFStringRef
    cdef CFStringRef vid_key_cf = _py_str_to_cfstring(USB_VENDOR_ID_KEY)
    if vid_key_cf == NULL:
        CFRelease(vid_cf)
        CFRelease(matching_dict)
        IONotificationPortDestroy(g_notify_port)
        g_notify_port = NULL
        raise IOKitError("Failed to create CFString for Vendor ID key")
    CFDictionarySetValue(matching_dict, vid_key_cf, vid_cf)
    CFRelease(vid_key_cf)
    CFRelease(vid_cf)

    # Add Product ID to matching dictionary
    cdef long product_id_val = pid
    cdef CFNumberRef pid_cf = CFNumberCreate(kCFAllocatorDefault, kCFNumberLongType, &product_id_val)
    if pid_cf == NULL:
        CFRelease(matching_dict)
        IONotificationPortDestroy(g_notify_port)
        g_notify_port = NULL
        raise IOKitError("CFNumberCreate failed for Product ID")

    cdef CFStringRef pid_key_cf = _py_str_to_cfstring(USB_PRODUCT_ID_KEY)
    if pid_key_cf == NULL:
        CFRelease(pid_cf)
        CFRelease(matching_dict)
        IONotificationPortDestroy(g_notify_port)
        g_notify_port = NULL
        raise IOKitError("Failed to create CFString for Product ID key")
    CFDictionarySetValue(matching_dict, pid_key_cf, pid_cf)
    CFRelease(pid_key_cf)
    CFRelease(pid_cf)
    print("[iokit_wrapper] VID and PID added to matching dictionary.")
    
    # matching_dict is now fully populated.
    # IOServiceAddMatchingNotification consumes the dictionary, so we don't release it here.

    # --- Register for Matched (Connect) Notifications ---
    print("[iokit_wrapper] Registering for Matched (Connect) Notifications...")
    # Pass 1 (True) as refCon for connected events
    cdef kern_return_t kr = IOServiceAddMatchingNotification(
        g_notify_port,
        K_IO_MATCHED_NOTIFICATION,
        matching_dict, # This matching_dict is consumed
        _usb_device_event_callback,
        <void*>1, # refCon for "connected"
        &g_matched_iterator
    )
    print(f"[iokit_wrapper] IOServiceAddMatchingNotification (connect) result: {kr}, iterator (addr): {<Py_ssize_t>g_matched_iterator}")
    if kr != KERN_SUCCESS:
        # If AddMatchingNotification fails, it does NOT consume the dictionary.
        CFRelease(matching_dict) 
        IONotificationPortDestroy(g_notify_port)
        g_notify_port = NULL
        raise IOKitError(f"IOServiceAddMatchingNotification (connect) failed: {kr}")

    # Process initially connected devices
    print("[iokit_wrapper] Processing initially connected devices (connect)...")
    _usb_device_event_callback(<void*>1, g_matched_iterator)
    print("[iokit_wrapper] Finished processing initially connected devices (connect).")

    # --- Register for Terminated (Disconnect) Notifications ---
    print("[iokit_wrapper] Terminated (Disconnect) Notifications are currently commented out.")
    # Temporarily commented out to isolate the kIOReturnExclusiveAccess error
    # matching_dict_term = IOServiceMatching(b"IOUSBDevice") # Match IOUSBDevice
    # if matching_dict_term == NULL:
    #     stop_usb_monitoring() # Attempt to clean up
    #     raise IOKitError("IOServiceMatching failed for terminated notifications")

    # # Populate with VID/PID again
    # vid_cf_term = CFNumberCreate(kCFAllocatorDefault, kCFNumberLongType, &vendor_id_val) # Use different var names
    # pid_cf_term = CFNumberCreate(kCFAllocatorDefault, kCFNumberLongType, &product_id_val)
    # vid_key_cf_term = _py_str_to_cfstring(USB_VENDOR_ID_KEY)
    # pid_key_cf_term = _py_str_to_cfstring(USB_PRODUCT_ID_KEY)

    # if not (vid_cf_term and pid_cf_term and vid_key_cf_term and pid_key_cf_term):
    #     if vid_cf_term: CFRelease(vid_cf_term)
    #     if pid_cf_term: CFRelease(pid_cf_term)
    #     if vid_key_cf_term: CFRelease(vid_key_cf_term)
    #     if pid_key_cf_term: CFRelease(pid_key_cf_term)
    #     CFRelease(matching_dict_term)
    #     stop_usb_monitoring()
    #     raise IOKitError("Failed to create CF objects for terminated matching dict (term)")

    # CFDictionarySetValue(matching_dict_term, vid_key_cf_term, vid_cf_term)
    # CFDictionarySetValue(matching_dict_term, pid_key_cf_term, pid_cf_term)
    # CFRelease(vid_key_cf_term); CFRelease(pid_key_cf_term); CFRelease(vid_cf_term); CFRelease(pid_cf_term)
    
    # # Pass 0 (False) as refCon for disconnected events
    # kr = IOServiceAddMatchingNotification(
    #     g_notify_port,
    #     K_IO_TERMINATED_NOTIFICATION,
    #     matching_dict_term, # This matching_dict is consumed
    #     _usb_device_event_callback,
    #     <void*>0, # refCon for "disconnected"
    #     &g_terminated_iterator
    # )
    # if kr != KERN_SUCCESS:
    #     CFRelease(matching_dict_term) # Not consumed on failure
    #     stop_usb_monitoring() # Attempt to clean up
    #     raise IOKitError(f"IOServiceAddMatchingNotification (disconnect) failed: {kr}")

    # # Process initially present devices that might have terminated (less common to iterate here)
    # _usb_device_event_callback(<void*>0, g_terminated_iterator)
    
    g_monitoring_active = True
    print("[iokit_wrapper] init_usb_monitoring: End (connect only).")
    # Return the address of the run loop source so Python side can manage it
    return <Py_ssize_t>g_run_loop_source

# def run_event_loop():
#     global g_event_loop_run_loop_ref, g_run_loop_source, g_monitoring_active
#     print("[iokit_wrapper] run_event_loop: Start")
    
#     if not g_monitoring_active or g_run_loop_source is NULL:
#         print("[iokit_wrapper] Error: Monitoring not active or run loop source is null in run_event_loop.")
#         return

#     # Get the RunLoop for the current thread (which should be the dedicated event thread)
#     g_event_loop_run_loop_ref = CFRunLoopGetCurrent()
#     print(f"[iokit_wrapper] CFRunLoopGetCurrent result (addr): {<Py_ssize_t>g_event_loop_run_loop_ref}")
#     if g_event_loop_run_loop_ref == NULL:
#         # This should not happen if called from a valid thread context
#         print("[iokit_wrapper] Error: Could not get current RunLoop in run_event_loop.")
#         return

#     CFRunLoopAddSource(g_event_loop_run_loop_ref, g_run_loop_source, kCFRunLoopDefaultMode)
#     print("[iokit_wrapper] Starting IOKit event loop (CFRunLoopRun)...")
#     CFRunLoopRun() # This blocks until CFRunLoopStop is called on this g_event_loop_run_loop_ref
#     print("[iokit_wrapper] IOKit event loop (CFRunLoopRun) finished.")
#     # Source is removed in stop_usb_monitoring

def stop_usb_monitoring():
    global g_notify_port, g_run_loop_source, g_event_loop_run_loop_ref # g_event_loop_run_loop_ref might become obsolete
    global g_matched_iterator, g_terminated_iterator, g_monitoring_active
    print("[iokit_wrapper] stop_usb_monitoring: Start")

    if not g_monitoring_active:
        print("[iokit_wrapper] USB monitoring is not active or already stopped.")
        return

    # CFRunLoopStop and CFRunLoopRemoveSource will be handled differently
    # when the source is added to the main run loop.
    # For now, we focus on releasing port and iterators.
    # The actual removal of the source from the main run loop will need to be
    # coordinated from the Python side (e.g., by calling a new Cython helper
    # or by using pyobjc to interact with the main NSRunLoop).

    # print("Attempting to stop USB monitoring...")
    # if g_event_loop_run_loop_ref != NULL: # This ref was for the dedicated thread's run loop
    #     print(f"[iokit_wrapper] Stopping RunLoop (addr): {<Py_ssize_t>g_event_loop_run_loop_ref}")
    #     CFRunLoopStop(g_event_loop_run_loop_ref) # No longer stopping a dedicated run loop here
    # else:
    #     print("[iokit_wrapper] g_event_loop_run_loop_ref is NULL, cannot stop RunLoop.")
    #     pass

    # Clean up resources
    print("[iokit_wrapper] Cleaning up IOKit resources (port, iterators)...")
    # If g_run_loop_source was added to the main loop, it needs to be removed from there first.
    # This function might be called when the app quits.
    # We'll assume for now that the main loop source removal is handled elsewhere or before this.
    # CFRunLoopRef mainRunLoop = CFRunLoopGetMain(); # Or the one rumps uses
    # if g_run_loop_source != NULL and mainRunLoop != NULL:
    #    print(f"[iokit_wrapper] Removing RunLoopSource (addr): {<Py_ssize_t>g_run_loop_source} from a RunLoop (TBD)")
    #    CFRunLoopRemoveSource(mainRunLoop, g_run_loop_source, kCFRunLoopDefaultMode)

    if g_notify_port != NULL:
        print(f"[iokit_wrapper] Destroying NotificationPort (addr): {<Py_ssize_t>g_notify_port}")
        IONotificationPortDestroy(g_notify_port)
        g_notify_port = NULL
        g_run_loop_source = NULL # It's invalidated when port is destroyed

    if g_matched_iterator != 0:
        print(f"[iokit_wrapper] Releasing matched_iterator (addr): {<Py_ssize_t>g_matched_iterator}")
        IOObjectRelease(g_matched_iterator)
        g_matched_iterator = 0
    
    if g_terminated_iterator != 0:
        print(f"[iokit_wrapper] Releasing terminated_iterator (addr): {<Py_ssize_t>g_terminated_iterator}")
        IOObjectRelease(g_terminated_iterator)
        g_terminated_iterator = 0

    g_python_callback_handler = None
    print("[iokit_wrapper] Python callback handler cleared.")
    g_event_loop_run_loop_ref = NULL
    g_monitoring_active = False
    print("[iokit_wrapper] stop_usb_monitoring: End. USB monitoring stopped and resources cleaned up.")


# --- Helper functions for adding/removing run loop source from Python ---
def add_run_loop_source_to_main_loop(Py_ssize_t source_addr):
    cdef CFRunLoopRef mainLoop = CFRunLoopGetMain() # Get the main application run loop
    cdef CFRunLoopSourceRef source = <CFRunLoopSourceRef>source_addr
    if mainLoop != NULL and source != NULL:
        CFRunLoopAddSource(mainLoop, source, kCFRunLoopDefaultMode)
        print(f"[iokit_wrapper] Added source (addr: {source_addr}) to main run loop (addr: {<Py_ssize_t>mainLoop}).")
        return True
    else:
        print(f"[iokit_wrapper] Failed to add source to main run loop. MainLoop (addr): {<Py_ssize_t>mainLoop}, Source (addr): {<Py_ssize_t>source}")
        return False

def remove_run_loop_source_from_main_loop(Py_ssize_t source_addr):
    cdef CFRunLoopRef mainLoop = CFRunLoopGetMain() # Get the main application run loop
    cdef CFRunLoopSourceRef source = <CFRunLoopSourceRef>source_addr
    if mainLoop != NULL and source != NULL:
        # It's important that the source is valid and actually part of this run loop.
        # CFRunLoopContainsSource might be used for checking, but CFRunLoopRemoveSource
        # should be safe even if not present (though it might log an error or do nothing).
        CFRunLoopRemoveSource(mainLoop, source, kCFRunLoopDefaultMode)
        print(f"[iokit_wrapper] Removed source (addr: {source_addr}) from main run loop (addr: {<Py_ssize_t>mainLoop}).")
        return True
    else:
        print(f"[iokit_wrapper] Failed to remove source from main run loop. MainLoop (addr): {<Py_ssize_t>mainLoop}, Source (addr): {<Py_ssize_t>source}")
        return False


# --- Original functions (get_service_properties, list_services, etc.) ---
# These are kept for now, but might need adjustments if types changed (e.g. CFDictionaryRef)

def get_service_properties(service_name: str, property_name: str = None):
    cdef io_iterator_t iterator = 0
    cdef io_service_t service = 0
    cdef kern_return_t result
    cdef CFMutableDictionaryRef cf_matching_dict = NULL
    cdef CFStringRef cf_prop_name_cfstr = NULL
    cdef CFTypeRef cf_prop_value = NULL
    
    service_name_bytes = service_name.encode('utf-8')
    properties = {}

    try:
        cf_matching_dict = <CFMutableDictionaryRef>IOServiceMatching(service_name_bytes)
        if cf_matching_dict == NULL:
            raise IOKitError(f"Failed to create matching dictionary for {service_name}")
        
        result = IOServiceGetMatchingServices(kIOMasterPortDefault, cf_matching_dict, &iterator)
        # IOServiceMatching creates a dict that we own.
        # IOServiceGetMatchingServices does NOT consume it according to some sources/examples.
        # So, we must release cf_matching_dict.
        
        if result != KERN_SUCCESS:
            raise IOKitError(f"Failed to get matching services: {result}")
        
        service = IOIteratorNext(iterator)
        if service == 0:
            raise IOKitError(f"No services found for {service_name}")
        
        if property_name:
            prop_name_bytes = property_name.encode('utf-8')
            cf_prop_name_cfstr = CFStringCreateWithCString(kCFAllocatorDefault, prop_name_bytes, kCFStringEncodingUTF8)
            if cf_prop_name_cfstr != NULL:
                cf_prop_value = IORegistryEntryCreateCFProperty(service, cf_prop_name_cfstr, kCFAllocatorDefault, 0)
                if cf_prop_value != NULL:
                    properties[property_name] = _convert_cf_to_python(cf_prop_value)
                    CFRelease(cf_prop_value)
        else:
            basic_props_list = ["IOPlatformSerialNumber", "model", "manufacturer", "product-name", "version"]
            for prop_str in basic_props_list:
                prop_bytes = prop_str.encode('utf-8')
                cf_prop_name_cfstr_loop = CFStringCreateWithCString(kCFAllocatorDefault, prop_bytes, kCFStringEncodingUTF8)
                if cf_prop_name_cfstr_loop != NULL:
                    cf_prop_value_loop = IORegistryEntryCreateCFProperty(service, cf_prop_name_cfstr_loop, kCFAllocatorDefault, 0)
                    if cf_prop_value_loop != NULL:
                        properties[prop_str] = _convert_cf_to_python(cf_prop_value_loop)
                        CFRelease(cf_prop_value_loop)
                    CFRelease(cf_prop_name_cfstr_loop)
        return properties
    finally:
        if service != 0: IOObjectRelease(service)
        if iterator != 0: IOObjectRelease(iterator)
        if cf_matching_dict != NULL: CFRelease(cf_matching_dict) # Release the matching dict
        if cf_prop_name_cfstr != NULL: CFRelease(cf_prop_name_cfstr) # If single property was used

def list_services(service_class_name: str = None):
    cdef io_iterator_t iterator = 0
    cdef io_service_t service = 0
    cdef kern_return_t result
    cdef CFMutableDictionaryRef cf_matching_dict = NULL
    py_services_list = []

    try:
        if service_class_name:
            service_class_bytes = service_class_name.encode('utf-8')
            cf_matching_dict = <CFMutableDictionaryRef>IOServiceMatching(service_class_bytes)
        else:
            cf_matching_dict = <CFMutableDictionaryRef>IOServiceMatching(b"IOService") # Generic base class
        
        if cf_matching_dict == NULL:
            raise IOKitError("Failed to create matching dictionary for list_services")
        
        result = IOServiceGetMatchingServices(kIOMasterPortDefault, cf_matching_dict, &iterator)
        if result != KERN_SUCCESS:
            raise IOKitError(f"Failed to get matching services for list_services: {result}")
        
        while True:
            service = IOIteratorNext(iterator)
            if service == 0: break
            # For now, just add a placeholder. Real implementation would get name.
            py_services_list.append(f"Service_{_get_service_id(service)}")
            IOObjectRelease(service)
        return py_services_list
    finally:
        if iterator != 0: IOObjectRelease(iterator)
        if cf_matching_dict != NULL: CFRelease(cf_matching_dict)


cdef _convert_cf_to_python(CFTypeRef cf_object):
    if cf_object == NULL: return None
    cdef unsigned long type_id = CFGetTypeID(cf_object)

    if type_id == CFStringGetTypeID():
        return _cfstring_to_python(<CFStringRef>cf_object)
    # Add more type conversions here (CFNumber, CFBoolean, CFData, CFDictionary, CFArray)
    # For now, return a string representation for unknown types
    return f"Unsupported CFType: ID {type_id}"


cdef _cfstring_to_python(CFStringRef cf_string): # Removed except? NULL
    if cf_string == NULL: return None
    
    cdef CFIndex length = CFStringGetLength(cf_string)
    cdef CFIndex buffer_size = length * 4 + 1 
    cdef char* c_buffer = <char*>malloc(buffer_size)
    if c_buffer == NULL:
        raise MemoryError("Failed to allocate buffer for CFString conversion")
    
    try:
        if CFStringGetCString(cf_string, c_buffer, buffer_size, kCFStringEncodingUTF8):
            return c_buffer.decode('utf-8')
        else:
            # This case should ideally raise an error or return a distinct value
            # For now, returning an error string, but Python None or Exception is better
            return "CFStringGetCString failed to convert string"
    finally:
        free(c_buffer)

# Original convenience functions
def get_system_serial():
    props = get_service_properties("IOPlatformExpertDevice", "IOPlatformSerialNumber")
    return props.get("IOPlatformSerialNumber", "Unknown")

def get_system_model():
    props = get_service_properties("IOPlatformExpertDevice", "model")
    return props.get("model", "Unknown")
