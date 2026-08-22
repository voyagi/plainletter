"""The file AgentCore Runtime starts.

The deployment zips this directory, so `plainletter` sits beside this file at the root of the
package and the runtime's own launcher runs it as a script. Everything it serves lives in the
package; this file only exists so the runtime has a fixed name to start.
"""

from plainletter.app import app

if __name__ == "__main__":
    app.run()
