import sys
import traceback
#from z_Main_Service.Logger import Logger # Implementation before release

from z_Builder.AppBuilder import AppBuilder

def main():
    """
      - Builds the app using AppBuilder (Qt app, event loop, GUI, model, controllers)
      - Runs the application
      - Catches and prints full tracebacks on exceptions
      - Ensures clean shutdown of app on exit
    """
    try:
        # Builder start
        builder = AppBuilder()
        app = (builder
               .with_qt_application()
               .with_event_loop()
               .with_gui_layer()
               .with_model_layer()
               .with_controllers()
               .build()
        )

        # App start
        exit_code = app.run()

    except Exception as e:
        print("Error starting application (full traceback): ", file=sys.stderr)
        traceback.print_exc()
        # short error summary
        print(f"\nSummary: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    finally:
        try:
            if app is not None:
                app.shutdown()
        except Exception:
            print("Error during shutdown (trace): ", file=sys.stderr)
            traceback.print_exc()
            pass

if __name__ == "__main__":
    sys.exit(main())

    

           #---Test----
       # analyzer = VideoAnalyzer(r"D:\CSGO2_projekt\samlpe_vids\fullmatches\overpass.mkv", skip_frames=15)
    # analyzer.run_analysis()