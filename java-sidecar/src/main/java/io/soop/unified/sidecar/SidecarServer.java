package io.soop.unified.sidecar;

import com.google.gson.Gson;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

public final class SidecarServer {
  private static final Gson GSON = new Gson();
  private final com.github.getcurrentthread.soopapi.SOOPClient soopapi = new com.github.getcurrentthread.soopapi.SOOPClient();
  private final zzik2.soop4j.SoopClient soop4j = zzik2.soop4j.SoopClient.builder().build();
  private final java.util.concurrent.ExecutorService providerExecutor = Executors.newVirtualThreadPerTaskExecutor();
  private static final long DEFAULT_PROVIDER_TIMEOUT_MS = 4000;
  private static final long MIN_PROVIDER_TIMEOUT_MS = 500;
  private static final long MAX_PROVIDER_TIMEOUT_MS = 10000;

  public static void main(String[] args) throws Exception { new SidecarServer().run(); }

  private void run() throws IOException {
    HttpServer server = HttpServer.create(new InetSocketAddress("0.0.0.0", 8091), 0);
    server.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
    server.createContext("/health", ex -> send(ex, 200, Map.of("ok", true, "service", "soop-unified-sidecar", "time", Instant.now().toString())));
    server.createContext("/v1/live", ex -> live(ex));
    server.createContext("/v1/channel", ex -> channel(ex));
    Runtime.getRuntime().addShutdownHook(new Thread(() -> { try { soopapi.close(); } catch (Exception ignored) {} providerExecutor.shutdownNow(); server.stop(0); }));
    server.start();
    System.out.println("[sidecar] listening on :8091");
  }

  private void live(HttpExchange ex) throws IOException {
    String id = validId(ex); if (id == null) return;
    long timeoutMs=providerTimeoutMs(ex);
    Map<String,Object> providers = new LinkedHashMap<>();
    var soopapiFuture = providerExecutor.submit(() -> observe(() -> {
      var x = await(soopapi.live().detail(id), timeoutMs);
      Map<String,Object> v = new LinkedHashMap<>();
      v.put("streamerId", id); v.put("online", x.result() != 0 && x.bno() != null && !x.bno().isBlank());
      put(v,"bno",x.bno()); put(v,"title",x.title()); put(v,"chatNo",x.chatNo()); put(v,"channelDomain",x.chatDomain()); put(v,"ftk",x.ftk());
      putInt(v,"channelPort",x.chatPort()); putInt(v,"bitrate",x.bps()); v.put("raw",x); return v;
    }));
    var soop4jFuture = providerExecutor.submit(() -> observe(() -> {
      var x = soop4j.live().detail(id);
      Map<String,Object> v = new LinkedHashMap<>();
      v.put("streamerId", id); v.put("online", x.isOnline()); put(v,"bno",x.getBroadcastNo()); put(v,"chatNo",x.getChatNo());
      put(v,"streamerNickname",x.getStreamerNick()); put(v,"title",x.getTitle()); put(v,"category",x.getCategory()); v.put("viewerCount",x.getViewerCount());
      put(v,"resolution",x.getResolution()); putInt(v,"bitrate",x.getBps()); put(v,"channelDomain",x.getChatDomain()); putInt(v,"channelPort",x.getChatPort()); put(v,"ftk",x.getFtk()); v.put("raw",x); return v;
    }));
    long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(timeoutMs);
    providers.put("soopapi", resolve(soopapiFuture, "soopapi", deadline, timeoutMs));
    providers.put("soop4j", resolve(soop4jFuture, "soop4j", deadline, timeoutMs));
    send(ex,200,Map.of("ok",true,"streamerId",id,"providers",providers));
  }

  private void channel(HttpExchange ex) throws IOException {
    String id = validId(ex); if (id == null) return;
    long timeoutMs=providerTimeoutMs(ex);
    Map<String,Object> providers = new LinkedHashMap<>();
    var soopapiFuture = providerExecutor.submit(() -> observe(() -> {
      var x = await(soopapi.channel().station(id), timeoutMs);
      Map<String,Object> v = new LinkedHashMap<>(); v.put("streamerId",id); put(v,"nickname",x.userNickname()); put(v,"stationName",x.stationName()); put(v,"stationTitle",x.stationTitle()); v.put("favorites",x.totalFollowers()); v.put("raw",x); return v;
    }));
    var soop4jFuture = providerExecutor.submit(() -> observe(() -> {
      var x = soop4j.channel().station(id); var st=x.getStation(); var b=x.getBroad(); var sub=x.getSubscription();
      Map<String,Object> v = new LinkedHashMap<>(); v.put("streamerId",id); put(v,"profileImage",x.getProfileImage());
      if(st!=null){put(v,"nickname",st.getUserNick());put(v,"stationName",st.getStationName());put(v,"stationTitle",st.getStationTitle());}
      if(b!=null){v.put("currentViewerCount",b.getCurrentSumViewer());v.put("broadNo",b.getBroadNo());put(v,"broadTitle",b.getBroadTitle());v.put("isPassword",b.isPassword());}
      if(sub!=null)v.put("subscribers",sub.getTotal()); v.put("raw",x); return v;
    }));
    long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(timeoutMs);
    providers.put("soopapi", resolve(soopapiFuture, "soopapi", deadline, timeoutMs));
    providers.put("soop4j", resolve(soop4jFuture, "soop4j", deadline, timeoutMs));
    send(ex,200,Map.of("ok",true,"streamerId",id,"providers",providers));
  }

  private static <T> T await(CompletableFuture<T> future,long timeoutMs) throws Exception {
    return future.get(timeoutMs, TimeUnit.MILLISECONDS);
  }

  private long providerTimeoutMs(HttpExchange ex){String raw=param(ex.getRequestURI(),"timeoutMs");if(raw==null)return DEFAULT_PROVIDER_TIMEOUT_MS;try{return Math.max(MIN_PROVIDER_TIMEOUT_MS,Math.min(MAX_PROVIDER_TIMEOUT_MS,Long.parseLong(raw)));}catch(Exception ignored){return DEFAULT_PROVIDER_TIMEOUT_MS;}}
  private String validId(HttpExchange ex) throws IOException { String id=param(ex.getRequestURI(),"id"); if(id==null||!id.matches("[A-Za-z0-9_-]{1,64}")){send(ex,400,Map.of("ok",false,"error","invalid id"));return null;} return id; }
  private Map<String,Object> observe(ThrowingSupplier f){long s=System.nanoTime();Map<String,Object> m=new LinkedHashMap<>();try{m.put("ok",true);m.put("value",f.get());}catch(Exception e){m.put("ok",false);m.put("error",e.getClass().getSimpleName()+": "+e.getMessage());}m.put("latencyMs",(System.nanoTime()-s)/1_000_000.0);return m;}
  private Map<String,Object> resolve(java.util.concurrent.Future<Map<String,Object>> future,String provider,long deadlineNanos,long timeoutMs){try{long remaining=Math.max(1,deadlineNanos-System.nanoTime());return future.get(remaining,TimeUnit.NANOSECONDS);}catch(Exception e){future.cancel(true);Map<String,Object> m=new LinkedHashMap<>();m.put("ok",false);m.put("error",provider+" timeout/failure: "+e.getClass().getSimpleName()+": "+String.valueOf(e.getMessage()));m.put("latencyMs",(double)timeoutMs);return m;}}
  private static void put(Map<String,Object> m,String k,String v){if(v!=null&&!v.isBlank())m.put(k,v);} private static void putInt(Map<String,Object> m,String k,String v){try{if(v!=null&&!v.isBlank())m.put(k,Integer.parseInt(v));}catch(Exception ignored){}}
  private static String param(URI uri,String key){String q=uri.getRawQuery();if(q==null)return null;for(String p:q.split("&")){String[] kv=p.split("=",2);if(kv.length==2&&kv[0].equals(key))return java.net.URLDecoder.decode(kv[1],StandardCharsets.UTF_8);}return null;}
  private static void send(HttpExchange ex,int status,Object body)throws IOException{byte[] b=GSON.toJson(body).getBytes(StandardCharsets.UTF_8);ex.getResponseHeaders().set("Content-Type","application/json; charset=utf-8");ex.sendResponseHeaders(status,b.length);try(var os=ex.getResponseBody()){os.write(b);}}
  @FunctionalInterface interface ThrowingSupplier { Object get() throws Exception; }
}
